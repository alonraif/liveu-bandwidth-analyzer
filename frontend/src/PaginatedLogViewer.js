import React, { useState, useEffect } from 'react';
import './PaginatedLogViewer.css';

const PaginatedLogViewer = ({
  file,
  dateRange,
  searchTerm,
  showLineNumbers,
  wrapText,
  token,
  onMetadataUpdate
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [linesPerPage, setLinesPerPage] = useState(1000);
  const [content, setContent] = useState('');
  const [metadata, setMetadata] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchResults, setSearchResults] = useState([]);
  const [currentSearchIndex, setCurrentSearchIndex] = useState(-1);

  const loadPage = async (page) => {
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('page', page.toString());
      formData.append('lines_per_page', linesPerPage.toString());

      if (dateRange?.startDate && dateRange?.startTime) {
        formData.append('start_datetime', `${dateRange.startDate} ${dateRange.startTime}`);
      }
      if (dateRange?.endDate && dateRange?.endTime) {
        formData.append('end_datetime', `${dateRange.endDate} ${dateRange.endTime}`);
      }

      const response = await fetch('/api/logs/chunked-content', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Failed to load page: ${response.statusText}`);
      }

      const data = await response.json();
      setContent(data.content);
      setMetadata(data);

      if (onMetadataUpdate && data.metadata) {
        onMetadataUpdate(data.metadata);
      }
    } catch (err) {
      setError(err.message);
      console.error('Error loading page:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (file) {
      setCurrentPage(1);
      loadPage(1);
    }
  }, [file, dateRange, linesPerPage]);

  useEffect(() => {
    loadPage(currentPage);
  }, [currentPage]);

  // Search functionality
  useEffect(() => {
    if (!searchTerm || !content) {
      setSearchResults([]);
      setCurrentSearchIndex(-1);
      return;
    }

    const lines = content.split('\n');
    const results = [];
    lines.forEach((line, lineIndex) => {
      const regex = new RegExp(searchTerm, 'gi');
      let match;
      while ((match = regex.exec(line)) !== null) {
        results.push({
          lineIndex,
          charIndex: match.index,
          match: match[0]
        });
      }
    });

    setSearchResults(results);
    setCurrentSearchIndex(results.length > 0 ? 0 : -1);
  }, [searchTerm, content]);

  const navigateSearch = (direction) => {
    if (searchResults.length === 0) return;

    let newIndex;
    if (direction === 'next') {
      newIndex = currentSearchIndex < searchResults.length - 1 ? currentSearchIndex + 1 : 0;
    } else {
      newIndex = currentSearchIndex > 0 ? currentSearchIndex - 1 : searchResults.length - 1;
    }
    setCurrentSearchIndex(newIndex);
  };

  const renderContent = () => {
    if (!content) return null;

    const lines = content.split('\n');
    const startLineNumber = metadata ? metadata.start_line : (currentPage - 1) * linesPerPage + 1;

    return lines.map((line, lineIndex) => {
      let displayLine = line;
      let isHighlighted = false;

      // Apply search highlighting
      if (searchTerm && searchResults.length > 0) {
        const lineResults = searchResults.filter(result => result.lineIndex === lineIndex);
        if (lineResults.length > 0) {
          const currentResult = searchResults[currentSearchIndex];
          isHighlighted = currentResult && currentResult.lineIndex === lineIndex;

          const regex = new RegExp(`(${searchTerm})`, 'gi');
          displayLine = line.replace(regex, (match) =>
            `<mark class="${isHighlighted ? 'current-match' : 'search-match'}">${match}</mark>`
          );
        }
      }

      return (
        <div key={lineIndex} className={`paginated-log-line ${isHighlighted ? 'current-line' : ''}`}>
          {showLineNumbers && (
            <span className="line-number">
              {startLineNumber + lineIndex}
            </span>
          )}
          <span
            className="line-content"
            style={{ whiteSpace: wrapText ? 'pre-wrap' : 'pre' }}
            dangerouslySetInnerHTML={{ __html: displayLine }}
          />
        </div>
      );
    });
  };

  const handlePageChange = (newPage) => {
    if (newPage >= 1 && metadata && newPage <= metadata.total_pages) {
      setCurrentPage(newPage);
    }
  };

  const handleLinesPerPageChange = (newLinesPerPage) => {
    setLinesPerPage(newLinesPerPage);
    setCurrentPage(1); // Reset to first page when changing page size
  };

  if (error) {
    return <div className="paginated-log-error">Error: {error}</div>;
  }

  return (
    <div className="paginated-log-viewer">
      {metadata && (
        <div className="pagination-controls">
          <div className="pagination-info">
            <span>
              Lines {metadata.start_line}-{metadata.end_line} of {metadata.total_lines}
              {metadata.total_pages > 1 && ` (Page ${currentPage} of ${metadata.total_pages})`}
            </span>
          </div>

          <div className="pagination-settings">
            <label>
              Lines per page:
              <select
                value={linesPerPage}
                onChange={(e) => handleLinesPerPageChange(parseInt(e.target.value))}
              >
                <option value={500}>500</option>
                <option value={1000}>1000</option>
                <option value={2000}>2000</option>
                <option value={5000}>5000</option>
              </select>
            </label>
          </div>

          {metadata.total_pages > 1 && (
            <div className="pagination-buttons">
              <button
                onClick={() => handlePageChange(1)}
                disabled={currentPage === 1 || loading}
                className="page-btn"
              >
                First
              </button>
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1 || loading}
                className="page-btn"
              >
                Previous
              </button>
              <span className="page-display">
                Page {currentPage} of {metadata.total_pages}
              </span>
              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === metadata.total_pages || loading}
                className="page-btn"
              >
                Next
              </button>
              <button
                onClick={() => handlePageChange(metadata.total_pages)}
                disabled={currentPage === metadata.total_pages || loading}
                className="page-btn"
              >
                Last
              </button>
            </div>
          )}

          {searchResults.length > 0 && (
            <div className="search-results">
              <span className="search-info">
                {searchResults.length} matches on this page
                {currentSearchIndex >= 0 && ` (${currentSearchIndex + 1} of ${searchResults.length})`}
              </span>
              <button
                onClick={() => navigateSearch('prev')}
                className="nav-button"
                disabled={searchResults.length === 0}
              >
                ▲
              </button>
              <button
                onClick={() => navigateSearch('next')}
                className="nav-button"
                disabled={searchResults.length === 0}
              >
                ▼
              </button>
            </div>
          )}
        </div>
      )}

      <div className="paginated-content">
        {loading ? (
          <div className="loading-indicator">Loading...</div>
        ) : (
          <div className={`log-content ${wrapText ? 'wrap-text' : 'no-wrap'}`}>
            {renderContent()}
          </div>
        )}
      </div>
    </div>
  );
};

export default PaginatedLogViewer;