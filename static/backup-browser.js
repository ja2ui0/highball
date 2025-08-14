/**
 * Backup Browser
 * Handles backup browsing for multiple provider types (Restic repositories, filesystem directories)
 */

// Provider configuration - defines endpoint patterns and terminology for different backup types
const PROVIDERS = {
    restic: {
        endpoints: {
            list: '/restic-snapshots',
            browse: '/restic-browse',
            stats: '/restic-snapshot-stats'
        },
        terminology: {
            unit: 'snapshot',
            units: 'snapshots',
            browser_title: 'Repository Browser',
            selection_label: 'Select Snapshot:'
        },
        supports_snapshots: true
    },
    rsync: {
        endpoints: {
            browse: '/filesystem-browse'
        },
        terminology: {
            browser_title: 'Filesystem Browser',
            selection_label: 'Browse Directory:'
        },
        supports_snapshots: false
    },
    rsyncd: {
        endpoints: {
            browse: '/filesystem-browse'
        },
        terminology: {
            browser_title: 'Filesystem Browser',
            selection_label: 'Browse Directory:'
        },
        supports_snapshots: false
    },
    ssh: {
        endpoints: {
            browse: '/filesystem-browse'
        },
        terminology: {
            browser_title: 'Filesystem Browser',
            selection_label: 'Browse Directory:'
        },
        supports_snapshots: false
    },
    local: {
        endpoints: {
            browse: '/filesystem-browse'
        },
        terminology: {
            browser_title: 'Filesystem Browser',
            selection_label: 'Browse Directory:'
        },
        supports_snapshots: false
    }
};

// Browser state
let backupSelection = {
    files: new Set(),
    directories: new Set()
};
let currentJob = '';
let currentJobType = '';
let currentSnapshot = '';
let currentSnapshots = [];
let currentPath = '/';
let expandedDirs = new Map();
let loadingDirs = new Set();
let isNavigatingToFolder = false;

// Job type detection from global jobTypes variable
function detectJobType(jobName) {
    if (window.jobTypes && window.jobTypes[jobName]) {
        return window.jobTypes[jobName];
    }
    return 'unknown';
}

// Multi-provider loading function
function loadBackupJob() {
    const backupJobSelect = document.getElementById('backupJobSelect');
    const browserContent = document.getElementById('browserContent');
    const repositoryInfo = document.getElementById('repositoryInfo');
    const snapshotSection = document.getElementById('snapshotSection');
    const errorDiv = document.getElementById('browserError');
    
    // Clear previous state
    hideAllSections();
    clearSelectionForNewJob();
    errorDiv.classList.add('hidden');
    
    if (backupJobSelect.value) {
        currentJob = backupJobSelect.value;
        currentJobType = detectJobType(currentJob);
        
        const provider = PROVIDERS[currentJobType];
        if (!provider) {
            showError(`Unsupported job type: ${currentJobType}`);
            return;
        }
        
        repositoryInfo.innerHTML = `<div class="loading">Loading ${provider.terminology.browser_title.toLowerCase()}...</div>`;
        browserContent.classList.remove('hidden');
        
        if (provider.supports_snapshots) {
            // Repository-based provider (Restic, Borg, etc.) - load snapshots
            fetch(`${provider.endpoints.list}?job=${encodeURIComponent(currentJob)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        populateSnapshots(data.snapshots, provider);
                        repositoryInfo.innerHTML = `<strong>${provider.terminology.browser_title}:</strong> ${currentJob} (${data.count} ${provider.terminology.units})`;
                        updateSnapshotSectionLabels(provider);
                        snapshotSection.classList.remove('hidden');
                    } else {
                        showError(`Failed to load ${provider.terminology.units}: ${data.error || 'Unknown error'}`);
                    }
                })
                .catch(error => {
                    showError(`Network error loading ${provider.terminology.units}: ${error.message}`);
                });
        } else {
            // Filesystem-based provider (rsync) - directly browse filesystem
            repositoryInfo.innerHTML = `<strong>${provider.terminology.browser_title}:</strong> ${currentJob}`;
            loadFilesystemRoot(provider);
        }
    } else {
        browserContent.classList.add('hidden');
        currentJob = '';
        currentJobType = '';
    }
}

function updateSnapshotSectionLabels(provider) {
    const title = document.getElementById('snapshotSectionTitle');
    if (title) {
        title.textContent = provider.terminology.selection_label;
    }
}

function loadFilesystemRoot(provider) {
    const fileTree = document.getElementById('fileTree');
    
    // Reset filesystem browser state
    expandedDirs.clear();
    loadingDirs.clear();
    currentPath = '/';
    isNavigatingToFolder = false;
    
    // Load root directory for filesystem browsing
    loadDirectoryIntoTree('/', provider);
    fileTree.classList.remove('hidden');
}

function populateSnapshots(snapshots, provider) {
    const snapshotSelect = document.getElementById('snapshotSelect');
    
    // Store snapshots globally
    currentSnapshots = snapshots || [];
    
    // Clear existing options except first
    snapshotSelect.innerHTML = `<option value="">Select a ${provider.terminology.unit}...</option>`;
    
    if (snapshots && snapshots.length > 0) {
        // Sort by time (newest first)
        snapshots.sort((a, b) => new Date(b.time) - new Date(a.time));
        
        // Handle scrolling for many snapshots (keep as dropdown, not listbox)
        
        snapshots.forEach(snapshot => {
            const option = document.createElement('option');
            option.value = snapshot.full_id;
            option.textContent = `${snapshot.id} - ${snapshot.time} (${snapshot.username}@${snapshot.hostname})`;
            snapshotSelect.appendChild(option);
        });
        
        // Don't pre-select - let user choose which snapshot to load
    }
}

function loadSnapshotDetails() {
    const snapshotSelect = document.getElementById('snapshotSelect');
    const detailsDiv = document.getElementById('snapshotDetails');
    const snapshotInfo = document.getElementById('snapshotInfo');
    const fileTree = document.getElementById('fileTree');
    
    // Clear selection when switching snapshots
    clearSelectionForNewJob();
    
    if (snapshotSelect.value) {
        currentSnapshot = snapshotSelect.value;
        
        // Find the actual snapshot data
        const currentSnapshotData = currentSnapshots.find(s => s.full_id === currentSnapshot);
        
        snapshotInfo.innerHTML = `
            <div><strong>Snapshot ID:</strong> ${currentSnapshot.substring(0, 8)}</div>
            <div><strong>Created:</strong> ${currentSnapshotData ? currentSnapshotData.time : 'unknown'}</div>
            <div><strong>User@Host:</strong> ${currentSnapshotData ? currentSnapshotData.username + '@' + currentSnapshotData.hostname : 'unknown'}</div>
            <div id="snapshotStatsLoading">Loading detailed statistics...</div>
        `;
        detailsDiv.classList.remove('hidden');
        
        // Fetch detailed snapshot statistics
        fetchSnapshotStatistics();
        
        // Reset tree state and load root
        expandedDirs.clear();
        loadingDirs.clear();
        currentPath = '/';
        isNavigatingToFolder = false;
        
        const provider = PROVIDERS[currentJobType];
        loadDirectoryIntoTree('/', provider);
        fileTree.classList.remove('hidden');
    } else {
        detailsDiv.classList.add('hidden');
        fileTree.classList.add('hidden');
        currentSnapshot = '';
    }
}

function fetchSnapshotStatistics() {
    if (!currentJob || !currentSnapshot || currentJobType !== 'restic') {
        return;
    }
    
    const provider = PROVIDERS[currentJobType];
    fetch(`${provider.endpoints.stats}?job=${encodeURIComponent(currentJob)}&snapshot=${encodeURIComponent(currentSnapshot)}`)
        .then(response => response.json())
        .then(data => {
            const loadingDiv = document.getElementById('snapshotStatsLoading');
            if (loadingDiv) {
                if (data.success && data.stats) {
                    const stats = data.stats;
                    loadingDiv.innerHTML = `
                        <div><strong>Files:</strong> ${formatNumber(stats.total_file_count)}</div>
                        <div><strong>Total Size:</strong> ${formatFileSize(stats.total_size)}</div>
                    `;
                } else {
                    loadingDiv.innerHTML = `<div style="color: var(--text-muted); font-style: italic;">Statistics unavailable: ${data.error || 'Unknown error'}</div>`;
                }
            }
        })
        .catch(error => {
            const loadingDiv = document.getElementById('snapshotStatsLoading');
            if (loadingDiv) {
                loadingDiv.innerHTML = `<div style="color: var(--text-muted); font-style: italic;">Statistics unavailable</div>`;
            }
        });
}

function formatNumber(num) {
    if (num == null) return '0';
    return new Intl.NumberFormat().format(num);
}

function loadDirectoryIntoTree(path, provider = null) {
    const treeContainer = document.getElementById('treeContainer');
    const errorDiv = document.getElementById('browserError');
    
    if (!provider) {
        provider = PROVIDERS[currentJobType];
        if (!provider) {
            showError('Unknown job type');
            return;
        }
    }
    
    errorDiv.classList.add('hidden');
    
    if (path === '/') {
        // Loading root - show loading message
        treeContainer.innerHTML = '<div class="loading">Loading directory contents...</div>';
    }
    
    if (loadingDirs.has(path)) {
        return; // Already loading
    }
    
    loadingDirs.add(path);
    
    let url;
    if (provider.supports_snapshots) {
        url = `${provider.endpoints.browse}?job=${encodeURIComponent(currentJob)}&snapshot=${encodeURIComponent(currentSnapshot)}&path=${encodeURIComponent(path)}`;
    } else {
        url = `${provider.endpoints.browse}?job=${encodeURIComponent(currentJob)}&path=${encodeURIComponent(path)}`;
    }
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            loadingDirs.delete(path);
            if (data.success) {
                expandedDirs.set(path, data.contents);
                if (path === '/') {
                    renderFullTree();
                } else {
                    // Re-render the tree to show newly loaded directory
                    renderFullTree();
                }
            } else {
                showError(`Failed to load directory: ${data.error || 'Unknown error'}`);
                if (path === '/') {
                    treeContainer.innerHTML = '';
                }
            }
        })
        .catch(error => {
            loadingDirs.delete(path);
            showError(`Network error loading directory: ${error.message}`);
            if (path === '/') {
                treeContainer.innerHTML = '';
            }
        });
}

function loadDirectoryIntoTreeWithoutLoadingCheck(path) {
    const treeContainer = document.getElementById('treeContainer');
    const errorDiv = document.getElementById('browserError');
    
    const provider = PROVIDERS[currentJobType];
    if (!provider) {
        showError('Unknown job type');
        return;
    }
    
    errorDiv.classList.add('hidden');
    
    if (path === '/') {
        // Loading root - show loading message
        treeContainer.innerHTML = '<div class="loading">Loading directory contents...</div>';
    }
    
    let url;
    if (provider.supports_snapshots) {
        url = `${provider.endpoints.browse}?job=${encodeURIComponent(currentJob)}&snapshot=${encodeURIComponent(currentSnapshot)}&path=${encodeURIComponent(path)}`;
    } else {
        url = `${provider.endpoints.browse}?job=${encodeURIComponent(currentJob)}&path=${encodeURIComponent(path)}`;
    }
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            loadingDirs.delete(path);
            if (data.success) {
                expandedDirs.set(path, data.contents);
                if (path === '/') {
                    renderFullTree();
                } else {
                    // Re-render the tree to show newly loaded directory
                    renderFullTree();
                }
            } else {
                showError(`Failed to load directory: ${data.error || 'Unknown error'}`);
                if (path === '/') {
                    treeContainer.innerHTML = '';
                }
            }
        })
        .catch(error => {
            loadingDirs.delete(path);
            showError(`Network error loading directory: ${error.message}`);
            if (path === '/') {
                treeContainer.innerHTML = '';
            }
        });
}

function renderFullTree() {
    const treeContainer = document.getElementById('treeContainer');
    
    if (isNavigatingToFolder) {
        // Folder navigation mode - show current folder contents with .. navigation
        renderFolderView();
        return;
    }
    
    if (!expandedDirs.has('/')) {
        treeContainer.innerHTML = '<div class="loading">Loading directory contents...</div>';
        return;
    }
    
    const rootContents = expandedDirs.get('/');
    if (!rootContents || rootContents.length === 0) {
        treeContainer.innerHTML = '<div class="empty-directory">Directory is empty</div>';
        return;
    }
    
    let html = '<ul class="file-tree">';
    
    // Add the tree items starting from root - hierarchical view
    html += renderTreeItems('/', 0);
    html += '</ul>';
    
    treeContainer.innerHTML = html;
}

function renderFolderView() {
    const treeContainer = document.getElementById('treeContainer');
    
    if (!expandedDirs.has(currentPath)) {
        treeContainer.innerHTML = '<div class="loading">Loading directory contents...</div>';
        return;
    }
    
    const contents = expandedDirs.get(currentPath);
    if (!contents || contents.length === 0) {
        treeContainer.innerHTML = '<div class="empty-directory">Directory is empty</div>';
        return;
    }
    
    let html = '<ul class="file-tree">';
    
    // Add ".." navigation if not at root
    if (currentPath !== '/') {
        const isSelected = backupSelection.directories.has('..');
        html += `
            <li class="tree-item parent">
                <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                       onchange="toggleSelection('..', 'directory', this.checked)">
<svg class="tree-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 10.5V16.5M15 13.5H9M13.0607 6.31066L10.9393 4.18934C10.658 3.90804 10.2765 3.75 9.87868 3.75H4.5C3.25736 3.75 2.25 4.75736 2.25 6V18C2.25 19.2426 3.25736 20.25 4.5 20.25H19.5C20.7426 20.25 21.75 19.2426 21.75 18V9C21.75 7.75736 20.7426 6.75 19.5 6.75H14.1213C13.7235 6.75 13.342 6.59197 13.0607 6.31066Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span class="tree-name" onclick="navigateToParent()">.. (Back to hierarchy view)</span>
            </li>
        `;
    }
    
    // Show current directory contents
    contents.forEach(item => {
        if (item.type === 'parent') return; // Skip server-generated parent entries
        
        const isSelected = backupSelection.files.has(item.path) || backupSelection.directories.has(item.path);
        
        if (item.type === 'directory') {
            html += `
                <li class="tree-item directory">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'directory', this.checked)">
<svg class="tree-icon clickable-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"
                         onclick="navigateToFolder('${escapeHtml(item.path)}')" title="Click to navigate into folder">
                        <path d="M12 10.5V16.5M15 13.5H9M13.0607 6.31066L10.9393 4.18934C10.658 3.90804 10.2765 3.75 9.87868 3.75H4.5C3.25736 3.75 2.25 4.75736 2.25 6V18C2.25 19.2426 3.25736 20.25 4.5 20.25H19.5C20.7426 20.25 21.75 19.2426 21.75 18V9C21.75 7.75736 20.7426 6.75 19.5 6.75H14.1213C13.7235 6.75 13.342 6.59197 13.0607 6.31066Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <span class="tree-name" onclick="navigateToFolder('${escapeHtml(item.path)}')">${escapeHtml(item.name)}</span>
                </li>
            `;
        } else {
            const size = item.size ? formatFileSize(item.size) : '';
            html += `
                <li class="tree-item file">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'file', this.checked)">
                    <svg class="tree-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19.5 14.25V11.625C19.5 9.76104 17.989 8.25 16.125 8.25H14.625C14.0037 8.25 13.5 7.74632 13.5 7.125V5.625C13.5 3.76104 11.989 2.25 10.125 2.25H8.25M10.5 2.25H5.625C5.00368 2.25 4.5 2.75368 4.5 3.375V20.625C4.5 21.2463 5.00368 21.75 5.625 21.75H18.375C18.9963 21.75 19.5 21.2463 19.5 20.625V11.25C19.5 6.27944 15.4706 2.25 10.5 2.25Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <span class="tree-name">${escapeHtml(item.name)}</span>
                    ${size ? `<span class="tree-size">${size}</span>` : ''}
                </li>
            `;
        }
    });
    
    html += '</ul>';
    treeContainer.innerHTML = html;
}

function renderTreeItems(path, depth, visitedPaths = new Set()) {
    // Prevent infinite recursion
    if (depth > 10) {
        return '';
    }
    
    if (visitedPaths.has(path)) {
        return '';
    }
    
    const contents = expandedDirs.get(path);
    if (!contents) return '';
    
    visitedPaths.add(path);
    let html = '';
    
    contents.forEach(item => {
        // Skip parent entries in recursive rendering
        if (item.type === 'parent') {
            return;
        }
        
        const isSelected = backupSelection.files.has(item.path) || backupSelection.directories.has(item.path);
        const selectedClass = isSelected ? ' selected' : '';
        const indentPx = depth * 20;
        
        if (item.type === 'directory') {
            const isExpanded = expandedDirs.has(item.path);
            const isLoading = loadingDirs.has(item.path);
            
            html += `
                <li class="tree-item directory${selectedClass}" style="padding-left: ${indentPx}px">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'directory', this.checked)">
${isExpanded ? 
                        `<svg class="tree-icon clickable-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"
                             onclick="toggleDirectory('${escapeHtml(item.path)}')" title="Click to collapse folder">
                            <path d="M15 13.5H9M13.0607 6.31066L10.9393 4.18934C10.658 3.90804 10.2765 3.75 9.87868 3.75H4.5C3.25736 3.75 2.25 4.75736 2.25 6V18C2.25 19.2426 3.25736 20.25 4.5 20.25H19.5C20.7426 20.25 21.75 19.2426 21.75 18V9C21.75 7.75736 20.7426 6.75 19.5 6.75H14.1213C13.7235 6.75 13.342 6.59197 13.0607 6.31066Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                         </svg>` :
                        `<svg class="tree-icon clickable-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"
                             onclick="toggleDirectory('${escapeHtml(item.path)}')" title="Click to expand folder">
                            <path d="M12 10.5V16.5M15 13.5H9M13.0607 6.31066L10.9393 4.18934C10.658 3.90804 10.2765 3.75 9.87868 3.75H4.5C3.25736 3.75 2.25 4.75736 2.25 6V18C2.25 19.2426 3.25736 20.25 4.5 20.25H19.5C20.7426 20.25 21.75 19.2426 21.75 18V9C21.75 7.75736 20.7426 6.75 19.5 6.75H14.1213C13.7235 6.75 13.342 6.59197 13.0607 6.31066Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                         </svg>`}
                    <span class="tree-name" onclick="navigateToFolder('${escapeHtml(item.path)}')">${escapeHtml(item.name)}</span>
                    ${isLoading ? '<span class="loading-indicator">Loading...</span>' : ''}
                </li>
            `;
            
            // Render children if expanded or loading placeholder if loading
            if (isExpanded) {
                html += renderTreeItems(item.path, depth + 1, visitedPaths);
            } else if (isLoading) {
                // Show loading placeholder content
                const childIndentPx = (depth + 1) * 20;
                html += `
                    <li class="tree-item loading-placeholder" style="padding-left: ${childIndentPx}px">
                        <span style="color: var(--text-muted); font-style: italic;">Loading contents...</span>
                    </li>
                `;
            }
        } else {
            const size = item.size ? formatFileSize(item.size) : '';
            html += `
                <li class="tree-item file${selectedClass}" style="padding-left: ${indentPx}px">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''}
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'file', this.checked)">
                    <svg class="tree-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19.5 14.25V11.625C19.5 9.76104 17.989 8.25 16.125 8.25H14.625C14.0037 8.25 13.5 7.74632 13.5 7.125V5.625C13.5 3.76104 11.989 2.25 10.125 2.25H8.25M10.5 2.25H5.625C5.00368 2.25 4.5 2.75368 4.5 3.375V20.625C4.5 21.2463 5.00368 21.75 5.625 21.75H18.375C18.9963 21.75 19.5 21.2463 19.5 20.625V11.25C19.5 6.27944 15.4706 2.25 10.5 2.25Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <span class="tree-name">${escapeHtml(item.name)}</span>
                    ${size ? `<span class="tree-size">${size}</span>` : ''}
                </li>
            `;
        }
    });
    
    visitedPaths.delete(path);
    return html;
}

function toggleDirectory(path) {
    if (expandedDirs.has(path)) {
        // Collapse directory
        expandedDirs.delete(path);
        renderFullTree();
    } else {
        // If it's currently loading, clear the loading state and try again
        if (loadingDirs.has(path)) {
            loadingDirs.delete(path);
        }
        
        // Expand directory - show loading indicator immediately
        loadingDirs.add(path);
        renderFullTree(); // Show loading indicator
        
        // Then load contents (but don't add to loadingDirs again)
        loadDirectoryIntoTreeWithoutLoadingCheck(path);
    }
}

function navigateToFolder(path) {
    // Navigate to folder view - show only this folder's contents
    currentPath = path;
    isNavigatingToFolder = true;
    
    // Load this directory if not already loaded
    if (!expandedDirs.has(path)) {
        loadDirectoryIntoTree(path);
    } else {
        renderFullTree();
    }
}

function navigateToParent() {
    // Return to hierarchical view
    isNavigatingToFolder = false;
    currentPath = '/';
    renderFullTree();
}

function toggleSelection(path, type, isChecked) {
    if (isChecked) {
        if (type === 'directory') {
            backupSelection.directories.add(path);
        } else {
            backupSelection.files.add(path);
        }
    } else {
        backupSelection.directories.delete(path);
        backupSelection.files.delete(path);
    }
    
    updateSelectionDisplay();
}

function clearSelection() {
    backupSelection.files.clear();
    backupSelection.directories.clear();
    updateSelectionDisplay();
    
    // Re-render tree to update selection state if we're not navigating
    if (!isNavigatingToFolder) {
        renderFullTree();
    }
}

function clearSelectionForNewJob() {
    // Use this when changing jobs or snapshots
    backupSelection.files.clear();
    backupSelection.directories.clear();
    updateSelectionDisplay();
}

function updateSelectionDisplay() {
    const selectionInfo = document.getElementById('selectionInfo');
    const selectionCount = document.getElementById('selectionCount');
    const selectionList = document.getElementById('selectionList');
    const totalSelected = backupSelection.files.size + backupSelection.directories.size;
    
    if (totalSelected > 0) {
        selectionCount.textContent = `${backupSelection.files.size} files, ${backupSelection.directories.size} directories selected`;
        selectionInfo.classList.remove('hidden');
        
        // Update selection pane
        let html = '<ul class="selection-list">';
        
        // Add directories first
        backupSelection.directories.forEach(path => {
            const name = path === '..' ? '..' : path.split('/').pop() || path;
            html += `<li class="selection-item directory">${escapeHtml(name)}</li>`;
        });
        
        // Add files
        backupSelection.files.forEach(path => {
            const name = path.split('/').pop() || path;
            html += `<li class="selection-item file">${escapeHtml(name)}</li>`;
        });
        
        html += '</ul>';
        selectionList.innerHTML = html;
    } else {
        selectionInfo.classList.add('hidden');
        selectionList.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-style: italic;">No items selected</div>';
    }
}

function hideAllSections() {
    document.getElementById('snapshotSection').classList.add('hidden');
    document.getElementById('snapshotDetails').classList.add('hidden');
    document.getElementById('fileTree').classList.add('hidden');
}

function showError(message) {
    const errorDiv = document.getElementById('browserError');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions for potential future use
window.BackupBrowser = {
    loadBackupJob,
    loadSnapshotDetails,
    loadDirectoryIntoTree,
    navigateToFolder,
    toggleSelection,
    clearSelection,
    getSelection: () => backupSelection
};