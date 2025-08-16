/**
 * Add Job Form JavaScript
 * Handles form field visibility and cron pattern display for job creation
 */

function showCronField() {
    const schedule = document.getElementById('schedule').value;
    const cronField = document.getElementById('cron_field');
    if (schedule === 'cron') {
        cronField.style.display = 'block';
    } else {
        cronField.style.display = 'none';
    }
}