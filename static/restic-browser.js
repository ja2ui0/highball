/**
 * Restic Repository Browser
 * Handles repository browsing, snapshot listing, and file tree navigation
 */

// Restic browser state
let resticSelection = {
    files: new Set(),
    directories: new Set()
};
let currentJob = '';
let currentSnapshot = '';
let currentPath = '/';
let expandedDirs = new Map(); // Track expanded directories and their contents
let loadingDirs = new Set(); // Track directories currently being loaded
let isNavigatingToFolder = false; // Track if we're in folder navigation mode

// Progressive loading functions
function loadResticRepository() {
    const resticJobSelect = document.getElementById('resticJobSelect');
    const browserContent = document.getElementById('resticBrowserContent');
    const repositoryInfo = document.getElementById('resticRepositoryInfo');
    const snapshotSection = document.getElementById('resticSnapshotSection');
    const errorDiv = document.getElementById('resticError');
    
    // Clear previous state
    hideAllSections();
    clearSelectionForNewSnapshot();
    errorDiv.classList.add('hidden');
    
    if (resticJobSelect.value) {
        currentJob = resticJobSelect.value;
        
        repositoryInfo.innerHTML = '<div class="loading">Loading repository information...</div>';
        browserContent.classList.remove('hidden');
        
        // Load snapshots for this job
        fetch(`/restic-snapshots?job=${encodeURIComponent(currentJob)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    populateSnapshots(data.snapshots);
                    repositoryInfo.innerHTML = `<strong>Repository:</strong> ${currentJob} (${data.count} snapshots)`;
                    snapshotSection.classList.remove('hidden');
                } else {
                    showError(`Failed to load snapshots: ${data.error || 'Unknown error'}`);
                }
            })
            .catch(error => {
                showError(`Network error loading snapshots: ${error.message}`);
            });
    } else {
        browserContent.classList.add('hidden');
        currentJob = '';
    }
}

function populateSnapshots(snapshots) {
    const snapshotSelect = document.getElementById('resticSnapshotSelect');
    
    // Clear existing options except first
    snapshotSelect.innerHTML = '<option value="">Select a snapshot...</option>';
    
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
    const snapshotSelect = document.getElementById('resticSnapshotSelect');
    const detailsDiv = document.getElementById('resticSnapshotDetails');
    const snapshotInfo = document.getElementById('snapshotInfo');
    const fileTree = document.getElementById('resticFileTree');
    
    // Clear selection when switching snapshots - this should clear everything
    clearSelectionForNewSnapshot();
    
    if (snapshotSelect.value) {
        currentSnapshot = snapshotSelect.value;
        
        // Show snapshot details
        const selectedOption = snapshotSelect.options[snapshotSelect.selectedIndex];
        snapshotInfo.innerHTML = `
            <div><strong>Snapshot ID:</strong> ${currentSnapshot.substring(0, 8)}</div>
            <div><strong>Created:</strong> ${selectedOption.textContent.split(' - ')[1]}</div>
        `;
        detailsDiv.classList.remove('hidden');
        
        // Reset tree state and load root
        expandedDirs.clear();
        loadingDirs.clear();
        currentPath = '/';
        isNavigatingToFolder = false;
        loadDirectoryIntoTree('/');
        fileTree.classList.remove('hidden');
    } else {
        detailsDiv.classList.add('hidden');
        fileTree.classList.add('hidden');
        currentSnapshot = '';
    }
}

function loadDirectoryIntoTree(path) {
    const treeContainer = document.getElementById('resticTreeContainer');
    const errorDiv = document.getElementById('resticError');
    
    errorDiv.classList.add('hidden');
    
    if (path === '/') {
        // Loading root - show loading message
        treeContainer.innerHTML = '<div class="loading">Loading directory contents...</div>';
    }
    
    if (loadingDirs.has(path)) {
        return; // Already loading
    }
    
    loadingDirs.add(path);
    
    fetch(`/restic-browse?job=${encodeURIComponent(currentJob)}&snapshot=${encodeURIComponent(currentSnapshot)}&path=${encodeURIComponent(path)}`)
        .then(response => response.json())
        .then(data => {
            loadingDirs.delete(path);
            if (data.success) {
                console.log(`Loaded directory ${path}:`, data.contents.length, 'items');
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
    const treeContainer = document.getElementById('resticTreeContainer');
    
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
    const treeContainer = document.getElementById('resticTreeContainer');
    
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
        const isSelected = resticSelection.directories.has('..');
        html += `
            <li class="tree-item parent">
                <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                       onchange="toggleSelection('..', 'directory', this.checked)">
                <img src="/static/icons/folder-plus.svg" class="tree-icon" alt="parent directory">
                <span class="tree-name" onclick="navigateToParent()">.. (Back to hierarchy view)</span>
            </li>
        `;
    }
    
    // Show current directory contents
    contents.forEach(item => {
        if (item.type === 'parent') return; // Skip server-generated parent entries
        
        const isSelected = resticSelection.files.has(item.path) || resticSelection.directories.has(item.path);
        
        if (item.type === 'directory') {
            html += `
                <li class="tree-item directory">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'directory', this.checked)">
                    <img src="/static/icons/folder-plus.svg" class="tree-icon clickable-icon" 
                         alt="folder" onclick="navigateToFolder('${escapeHtml(item.path)}')"
                         title="Click to navigate into folder">
                    <span class="tree-name" onclick="navigateToFolder('${escapeHtml(item.path)}')">${escapeHtml(item.name)}</span>
                </li>
            `;
        } else {
            const size = item.size ? formatFileSize(item.size) : '';
            html += `
                <li class="tree-item file">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'file', this.checked)">
                    <img src="/static/icons/document.svg" class="tree-icon" alt="file">
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
        
        const isSelected = resticSelection.files.has(item.path) || resticSelection.directories.has(item.path);
        const selectedClass = isSelected ? ' selected' : '';
        const indentPx = depth * 20;
        
        if (item.type === 'directory') {
            const isExpanded = expandedDirs.has(item.path);
            const isLoading = loadingDirs.has(item.path);
            
            html += `
                <li class="tree-item directory${selectedClass}" style="padding-left: ${indentPx}px">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''} 
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'directory', this.checked)">
                    <img src="/static/icons/${isExpanded ? 'folder-minus.svg' : 'folder-plus.svg'}" 
                         class="tree-icon clickable-icon" 
                         alt="${isExpanded ? 'open folder' : 'closed folder'}"
                         onclick="toggleDirectory('${escapeHtml(item.path)}')"
                         title="Click to ${isExpanded ? 'collapse' : 'expand'} folder">
                    <span class="tree-name" onclick="navigateToFolder('${escapeHtml(item.path)}')">${escapeHtml(item.name)}</span>
                    ${isLoading ? '<span class="loading-indicator">⋯</span>' : ''}
                </li>
            `;
            
            // Render children if expanded
            if (isExpanded) {
                html += renderTreeItems(item.path, depth + 1, visitedPaths);
            }
        } else {
            const size = item.size ? formatFileSize(item.size) : '';
            html += `
                <li class="tree-item file${selectedClass}" style="padding-left: ${indentPx}px">
                    <input type="checkbox" class="tree-checkbox" ${isSelected ? 'checked' : ''}
                           onchange="toggleSelection('${escapeHtml(item.path)}', 'file', this.checked)">
                    <img src="/static/icons/document.svg" class="tree-icon" alt="file">
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
        // Expand directory - load contents
        loadDirectoryIntoTree(path);
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
            resticSelection.directories.add(path);
        } else {
            resticSelection.files.add(path);
        }
    } else {
        resticSelection.directories.delete(path);
        resticSelection.files.delete(path);
    }
    
    updateSelectionDisplay();
}

function clearSelection() {
    resticSelection.files.clear();
    resticSelection.directories.clear();
    updateSelectionDisplay();
    
    // Re-render tree to update selection state if we're not navigating
    if (!isNavigatingToFolder) {
        renderFullTree();
    }
}

function clearSelectionForNewSnapshot() {
    // Only use this when changing snapshots
    resticSelection.files.clear();
    resticSelection.directories.clear();
    updateSelectionDisplay();
}

function updateSelectionDisplay() {
    const selectionInfo = document.getElementById('resticSelectionInfo');
    const selectionCount = document.getElementById('selectionCount');
    const totalSelected = resticSelection.files.size + resticSelection.directories.size;
    
    if (totalSelected > 0) {
        selectionCount.textContent = `${resticSelection.files.size} files, ${resticSelection.directories.size} directories selected`;
        selectionInfo.classList.remove('hidden');
    } else {
        selectionInfo.classList.add('hidden');
    }
}

function hideAllSections() {
    document.getElementById('resticSnapshotSection').classList.add('hidden');
    document.getElementById('resticSnapshotDetails').classList.add('hidden');
    document.getElementById('resticFileTree').classList.add('hidden');
}

function showError(message) {
    const errorDiv = document.getElementById('resticError');
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
window.ResticBrowser = {
    loadResticRepository,
    loadSnapshotDetails,
    loadDirectory,
    navigateToDirectory,
    toggleSelection,
    clearSelection,
    getSelection: () => resticSelection
};