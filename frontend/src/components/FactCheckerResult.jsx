import { motion, AnimatePresence } from 'framer-motion';

export default function FactCheckerResult({ result }) {
  if (!result) return null;

  const apiErrors = result.api_errors || [];

  // If any API failed, show a clean server-down message
  if (apiErrors.length > 0) {
    return (
      <AnimatePresence mode="wait">
        <motion.div
          className="result"
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          style={{ textAlign: 'center', padding: '2rem' }}
        >
          <p style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚠️</p>
          <h2 style={{ marginBottom: '0.5rem' }}>API Server is Down</h2>
          <p style={{ color: '#888', fontSize: '0.95em' }}>Please try again later.</p>
        </motion.div>
      </AnimatePresence>
    );
  }

  // Handle both old and new response formats
  const status = result.status || result.verdict || 'Unknown';
  const claim = result.claim_text || '';
  const explanation = result.explanation || result.response_text || '';
  const sources = result.sources || [];
  const findings = result.findings || [];
  const cached = result.cached || false;
  const cacheNote = result.cache_note || '';

  // Multimodal-specific fields
  const mediaType = result.media_type || null;
  const mediaFilename = result.media_filename || null;
  const extractedText = result.extracted_text || null;

  // URL-specific fields
  const url = result.url || null;
  const articleTitle = result.article_title || null;
  const articleSource = result.article_source || null;
  const articlePreview = result.article_preview || null;

  // Helper: extract domain from URL
  const extractDomain = (urlStr) => {
    try {
      const u = new URL(urlStr.startsWith('http') ? urlStr : `https://${urlStr}`);
      return u.hostname.replace('www.', '');
    } catch {
      return urlStr;
    }
  };

  // Helper: render a source item as a clickable link or plain text
  const renderSource = (source) => {
    if (!source) return null;
    const urlMatch = source.match(/(https?:\/\/[^\s)]+)/);
    if (urlMatch) {
      const sourceUrl = urlMatch[1];
      const domain = extractDomain(sourceUrl);
      // Strip the URL, brackets, and reference numbers like [1] from the label
      const label = source.replace(urlMatch[0], '').replace(/[\[\]()]/g, '').replace(/^\s*\d+\s*/, '').trim();
      // Only use label if it's meaningful (more than 2 chars, not just punctuation)
      const meaningfulLabel = label.length > 2 && !/^[\d\s.—-]+$/.test(label) ? label : '';
      return (
        <a href={sourceUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#4A90E2', textDecoration: 'none' }}>
          {meaningfulLabel ? `${meaningfulLabel} — ${domain}` : domain}
        </a>
      );
    }
    return <span>{source}</span>;
  };

  // Animation variants
  const containerVariants = {
    hidden: { opacity: 0, y: 50 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.6,
        ease: [0.22, 1, 0.36, 1],
        staggerChildren: 0.1
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, x: -20 },
    visible: {
      opacity: 1,
      x: 0,
      transition: { duration: 0.4, ease: "easeOut" }
    }
  };

  // Get media type emoji
  const getMediaEmoji = (type) => {
    if (type?.startsWith('image/')) return '📸';
    if (type?.startsWith('video/')) return '🎥';
    if (type?.startsWith('audio/')) return '🎤';
    return '📄';
  };

  // Helper function to render text with clickable URLs
  const renderTextWithLinks = (text) => {
    if (!text) return null;

    // Regular expression to match URLs
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);

    return parts.map((part, index) => {
      if (part.match(urlRegex)) {
        return (
          <a
            key={index}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#4A90E2', textDecoration: 'underline' }}
          >
            {part}
          </a>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <AnimatePresence mode="wait">
      <motion.div
        className="result"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        exit="hidden"
        key={result.claim_text}
      >
        <motion.h2
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        >
          Fact-Check Result
        </motion.h2>

        {url && (
          <motion.div className="result-section url-info" variants={itemVariants}>
            <strong>🔗 Source URL:</strong>
            <p>
              <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: '#4A90E2' }}>
                {url}
              </a>
            </p>
            {articleTitle && (
              <p style={{ marginTop: '0.5rem' }}>
                <strong>Article:</strong> {articleTitle}
              </p>
            )}
            {articleSource && (
              <p style={{ marginTop: '0.25rem', fontSize: '0.9em', color: '#666' }}>
                <strong>Publisher:</strong> {articleSource}
              </p>
            )}
          </motion.div>
        )}

        {mediaType && mediaFilename && (
          <motion.div className="result-section media-info" variants={itemVariants}>
            <strong>{getMediaEmoji(mediaType)} Media File:</strong>
            <p>{mediaFilename}</p>
          </motion.div>
        )}

        <motion.div className="result-section" variants={itemVariants}>
          <strong>Claim:</strong>
          <p>{claim}</p>
        </motion.div>

        <motion.div className="result-section" variants={itemVariants}>
          <strong>Status:</strong>
          <motion.p
            className="status"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5, type: "spring", stiffness: 200 }}
          >
            {status}
          </motion.p>
        </motion.div>

        {explanation && (
          <motion.div className="result-section" variants={itemVariants}>
            <strong>Explanation:</strong>
            <p>{renderTextWithLinks(explanation)}</p>
          </motion.div>
        )}

        {findings && findings.length > 0 && (
          <motion.div className="result-section" variants={itemVariants}>
            <strong>Key Findings:</strong>
            <ul>
              {findings.map((finding, index) => (
                <motion.li
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + index * 0.1 }}
                >
                  {renderTextWithLinks(finding)}
                </motion.li>
              ))}
            </ul>
          </motion.div>
        )}

        {sources && sources.length > 0 && (
          <motion.div className="result-section" variants={itemVariants}>
            <strong>Sources:</strong>
            <ul className="sources-list">
              {sources.map((source, index) => (
                <motion.li
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 + index * 0.1 }}
                >
                  {renderSource(source)}
                </motion.li>
              ))}
            </ul>
          </motion.div>
        )}

        {cached && cacheNote && (
          <motion.div
            className="result-section cache-note"
            variants={itemVariants}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.7 }}
          >
            <small>{cacheNote}</small>
          </motion.div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}

