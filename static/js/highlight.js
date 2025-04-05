document.addEventListener('DOMContentLoaded', function() {
    // Handle view match button clicks
    document.querySelectorAll('.view-match-btn').forEach(function(button) {
        button.addEventListener('click', function() {
            var item = this.getAttribute('data-item');
            document.getElementById('modalItemText').textContent = item;
            document.getElementById('matchExcerpt').innerHTML = '<div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">Loading...</span></div> Fetching match details...';
            
            // Hide the highlight explanation initially
            const highlightExplanation = document.getElementById('highlightExplanation');
            if (highlightExplanation) {
                highlightExplanation.style.display = 'none';
            }
            
            // Fetch the match details
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
                        const highlightColors = ['#c2f0c2', '#d6f5d6', '#e6ffe6']; // Different shades of green
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
                            result += `<span class="highlight" style="background-color: ${color}; font-weight: bold;">${match.term}</span>`;
                            
                            lastPos = match.end;
                            colorIndex++;
                        });
                        
                        // Add any remaining text
                        result += data.excerpt.substring(lastPos);
                        
                        // Display the highlighted excerpt
                        document.getElementById('matchExcerpt').innerHTML = result;
                        
                        // Show explanation of highlighted terms if matches were found
                        if (highlightExplanation && filteredMatches.length > 0) {
                            highlightExplanation.style.display = 'block';
                        }
                    } else {
                        document.getElementById('matchExcerpt').textContent = 'No specific excerpt available. The item was detected through pattern matching.';
                        if (highlightExplanation) {
                            highlightExplanation.style.display = 'none';
                        }
                    }
                })
                .catch(error => {
                    document.getElementById('matchExcerpt').textContent = 'Error fetching match details. Please try again.';
                    if (highlightExplanation) {
                        highlightExplanation.style.display = 'none';
                    }
                    console.error('Error:', error);
                });
        });
    });
});