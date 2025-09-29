import React, { useState, useEffect, useRef, useCallback } from 'react';
import './VirtualLogViewer.css';

const VirtualLogViewer = ({
  logContent,
  searchTerm,
  searchResults,
  currentSearchIndex,
  showLineNumbers,
  wrapText,
  onSearch
}) => {
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: 100 });
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef(null);
  const contentRef = useRef(null);

  const LINE_HEIGHT = 20; // Height of each line in pixels
  const BUFFER_SIZE = 50; // Extra lines to render above/below visible area

  const lines = logContent ? logContent.split('\n') : [];
  const totalLines = lines.length;

  const calculateVisibleRange = useCallback((scrollTop) => {
    const containerHeight = containerRef.current?.clientHeight || 400;
    const visibleLines = Math.ceil(containerHeight / LINE_HEIGHT);

    const startLine = Math.max(0, Math.floor(scrollTop / LINE_HEIGHT) - BUFFER_SIZE);
    const endLine = Math.min(totalLines, startLine + visibleLines + (BUFFER_SIZE * 2));

    return { start: startLine, end: endLine };
  }, [totalLines]);

  const handleScroll = useCallback((e) => {
    const newScrollTop = e.target.scrollTop;
    setScrollTop(newScrollTop);

    const newRange = calculateVisibleRange(newScrollTop);
    if (newRange.start !== visibleRange.start || newRange.end !== visibleRange.end) {
      setVisibleRange(newRange);
    }
  }, [calculateVisibleRange, visibleRange]);

  // Update visible range when content changes
  useEffect(() => {
    const newRange = calculateVisibleRange(scrollTop);
    setVisibleRange(newRange);
  }, [logContent, calculateVisibleRange, scrollTop]);

  // Scroll to search result
  useEffect(() => {
    if (searchResults.length > 0 && currentSearchIndex >= 0) {
      const currentResult = searchResults[currentSearchIndex];
      if (currentResult && containerRef.current) {
        const targetScrollTop = currentResult.lineIndex * LINE_HEIGHT;
        containerRef.current.scrollTop = targetScrollTop;
        setScrollTop(targetScrollTop);
      }
    }
  }, [currentSearchIndex, searchResults]);

  const renderVisibleLines = () => {
    const visibleLines = [];

    for (let i = visibleRange.start; i < visibleRange.end; i++) {
      if (i >= totalLines) break;

      const line = lines[i];
      let displayLine = line;
      let isHighlighted = false;

      // Apply search highlighting
      if (searchTerm && searchResults.length > 0) {
        const lineResults = searchResults.filter(result => result.lineIndex === i);
        if (lineResults.length > 0) {
          const currentResult = searchResults[currentSearchIndex];
          isHighlighted = currentResult && currentResult.lineIndex === i;

          const regex = new RegExp(`(${searchTerm})`, 'gi');
          displayLine = line.replace(regex, (match) =>
            `<mark class="${isHighlighted ? 'current-match' : 'search-match'}">${match}</mark>`
          );
        }
      }

      visibleLines.push(
        <div
          key={i}
          className={`virtual-log-line ${isHighlighted ? 'current-line' : ''}`}
          style={{
            position: 'absolute',
            top: i * LINE_HEIGHT,
            height: LINE_HEIGHT,
            left: 0,
            right: 0,
            display: 'flex',
            alignItems: 'center'
          }}
        >
          {showLineNumbers && (
            <span className="line-number" style={{ minWidth: '60px', textAlign: 'right', paddingRight: '10px' }}>
              {i + 1}
            </span>
          )}
          <span
            className="line-content"
            style={{ flex: 1, whiteSpace: wrapText ? 'pre-wrap' : 'pre' }}
            dangerouslySetInnerHTML={{ __html: displayLine }}
          />
        </div>
      );
    }

    return visibleLines;
  };

  if (!logContent) {
    return <div className="virtual-log-viewer">No content to display</div>;
  }

  return (
    <div
      ref={containerRef}
      className="virtual-log-viewer"
      onScroll={handleScroll}
      style={{
        height: '400px',
        overflow: 'auto',
        position: 'relative',
        border: '1px solid #ddd',
        fontFamily: 'monospace',
        fontSize: '12px'
      }}
    >
      <div
        ref={contentRef}
        style={{
          height: totalLines * LINE_HEIGHT,
          position: 'relative'
        }}
      >
        {renderVisibleLines()}
      </div>
    </div>
  );
};

export default VirtualLogViewer;