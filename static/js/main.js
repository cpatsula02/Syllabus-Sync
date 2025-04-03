document.addEventListener('DOMContentLoaded', function() {
    // Handle file uploads and show progress
    const uploadForm = document.getElementById('uploadForm');
    const submitBtn = document.getElementById('submitBtn');
    const uploadProgress = document.getElementById('uploadProgress');
    
    // Add null checks to prevent errors
    const progressBar = uploadProgress ? uploadProgress.querySelector('.progress-bar') : null;
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            // Check if files are selected
            const checklistFile = document.getElementById('checklist').files[0];
            const outlineFile = document.getElementById('outline').files[0];
            
            if (!checklistFile || !outlineFile) {
                e.preventDefault();
                alert('Please select both checklist and course outline files.');
                return;
            }
            
            // Check file types
            const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
            if (!allowedTypes.includes(checklistFile.type) || !allowedTypes.includes(outlineFile.type)) {
                e.preventDefault();
                alert('Only PDF and DOCX files are allowed.');
                return;
            }
            
            // Show progress
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            if (uploadProgress) {
                uploadProgress.classList.remove('d-none');
            }
            
            // Simulate progress (actual processing happens server-side)
            let progress = 0;
            const interval = setInterval(function() {
                progress += Math.random() * 10;
                if (progress >= 100) {
                    clearInterval(interval);
                    progress = 100;
                }
                
                // Only update progress if progressBar exists
                if (progressBar) {
                    progressBar.style.width = progress + '%';
                    progressBar.setAttribute('aria-valuenow', progress);
                    
                    if (progress === 100) {
                        progressBar.textContent = 'Analysis Complete!';
                    }
                }
            }, 300);
        });
    }
    
    // Copy to clipboard functionality for missing items
    const copyButtons = document.querySelectorAll('.copy-text');
    if (copyButtons.length > 0) {
        copyButtons.forEach(button => {
            button.addEventListener('click', function() {
                const textToCopy = this.getAttribute('data-text');
                
                // Create a temporary textarea element to copy from
                const textarea = document.createElement('textarea');
                textarea.value = textToCopy;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                
                // Change button text temporarily
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                }, 2000);
            });
        });
    }
    
    // Initialize progress circles on results page
    const progressCircles = document.querySelectorAll('.progress-circle');
    if (progressCircles.length > 0) {
        progressCircles.forEach(circle => {
            const value = circle.getAttribute('data-value');
            circle.style.setProperty('--progress', value + '%');
        });
    }
    
    // Print results functionality
    const printBtn = document.getElementById('printResults');
    if (printBtn) {
        printBtn.addEventListener('click', function() {
            window.print();
        });
    }
    
    // Highlight file input when dragging files
    const fileInputs = document.querySelectorAll('input[type=file]');
    if (fileInputs.length > 0) {
        fileInputs.forEach(input => {
            const container = input.closest('.upload-container');
            
            input.addEventListener('dragenter', function() {
                container.style.borderColor = 'var(--uofc-yellow)';
                container.style.backgroundColor = '#fff';
            });
            
            input.addEventListener('dragleave', function() {
                container.style.borderColor = '#ddd';
                container.style.backgroundColor = 'var(--uofc-light-gray)';
            });
            
            input.addEventListener('drop', function() {
                container.style.borderColor = 'var(--uofc-red)';
                container.style.backgroundColor = 'var(--uofc-light-gray)';
            });
            
            input.addEventListener('change', function() {
                if (this.files.length > 0) {
                    container.style.borderColor = 'var(--uofc-red)';
                    container.style.backgroundColor = 'var(--uofc-light-gray)';
                }
            });
        });
    }
});
