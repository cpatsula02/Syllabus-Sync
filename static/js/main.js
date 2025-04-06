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

// Function to load match details via AJAX
function loadMatchDetails(button) {
    const item = button.getAttribute('data-item');
    const evidenceBoxId = button.closest('.list-group-item').querySelector('.evidence-box').id;
    const evidenceBox = document.getElementById(evidenceBoxId);
    
    // Show the evidence box with loading spinner
    evidenceBox.style.display = 'block';
    
    // Fetch match details
    fetch('/get-match-details?item=' + encodeURIComponent(item))
        .then(response => response.json())
        .then(data => {
            if (data.found && data.excerpt) {
                // Extract key terms from the checklist item for highlighting
                const itemText = item.toLowerCase();
                const keyTerms = [];
                
                // Extract words longer than 3 letters, excluding common words
                const commonWords = ['and', 'the', 'that', 'this', 'with', 'from', 'have', 
                                  'for', 'are', 'should', 'would', 'could', 'will', 
                                  'been', 'must', 'they', 'their', 'there', 'than', 
                                  'when', 'what', 'where', 'which'];
                
                const words = itemText.match(/\b\w+\b/g) || [];
                words.forEach(word => {
                    if (word.length > 3 && !commonWords.includes(word)) {
                        keyTerms.push(word);
                    }
                });
                
                // Add special terms based on item content
                if (itemText.includes('email') || itemText.includes('contact')) {
                    keyTerms.push('@ucalgary.ca');
                }
                if (itemText.includes('late') || itemText.includes('deadline')) {
                    keyTerms.push('late', 'deadline', 'penalty');
                }
                if (itemText.includes('grade')) {
                    keyTerms.push('grade', 'grading', 'assessment', 'mark');
                }
                
                // Highlight the matching terms in the excerpt
                let highlightedExcerpt = data.excerpt;
                
                // Sort terms by length (longest first) to avoid highlighting parts of words
                keyTerms.sort((a, b) => b.length - a.length);
                
                // Create a safe version for case-insensitive matching
                const excerptLower = data.excerpt.toLowerCase();
                
                // Create spans with different highlight colors for better visibility
                const highlightColors = ['rgba(40, 167, 69, 0.3)', 'rgba(40, 167, 69, 0.2)', 'rgba(40, 167, 69, 0.15)']; // Different shades of green
                let colorIndex = 0;
                
                // First find all matches to avoid overlapping highlights
                const matches = [];
                keyTerms.forEach(term => {
                    const termLower = term.toLowerCase();
                    let startPos = 0;
                    while (startPos < excerptLower.length) {
                        const matchPos = excerptLower.indexOf(termLower, startPos);
                        if (matchPos === -1) break;
                        
                        matches.push({
                            start: matchPos,
                            end: matchPos + termLower.length,
                            term: data.excerpt.substring(matchPos, matchPos + termLower.length),
                            original: term
                        });
                        
                        startPos = matchPos + 1;
                    }
                });
                
                // Sort matches by position
                matches.sort((a, b) => a.start - b.start);
                
                // Remove overlapping matches
                const filteredMatches = [];
                let lastEnd = -1;
                
                matches.forEach(match => {
                    if (match.start >= lastEnd) {
                        filteredMatches.push(match);
                        lastEnd = match.end;
                    }
                });
                
                // Build the highlighted excerpt
                let result = '';
                let lastPos = 0;
                
                filteredMatches.forEach(match => {
                    // Add text before this match
                    result += data.excerpt.substring(lastPos, match.start);
                    
                    // Add the highlighted match
                    const color = highlightColors[colorIndex % highlightColors.length];
                    result += `<span class="highlight" style="background-color: ${color};">${match.term}</span>`;
                    
                    lastPos = match.end;
                    colorIndex++;
                });
                
                // Add any remaining text
                result += data.excerpt.substring(lastPos);
                
                // Add explanation about highlights
                const explanation = filteredMatches.length > 0 ? 
                    '<div class="mt-2 small text-muted"><i class="fas fa-info-circle me-1"></i>Green highlighted text shows matching content from the outline.</div>' : '';
                
                // Display the highlighted excerpt with explanation
                evidenceBox.innerHTML = result + explanation;
            } else {
                evidenceBox.innerHTML = '<div class="text-muted"><i class="fas fa-info-circle me-2"></i>No specific excerpt available. This item was detected through pattern matching or AI analysis.</div>';
            }
        })
        .catch(error => {
            evidenceBox.innerHTML = '<div class="text-danger"><i class="fas fa-exclamation-circle me-2"></i>Error loading match details. Please try again.</div>';
            console.error('Error:', error);
        });
}
