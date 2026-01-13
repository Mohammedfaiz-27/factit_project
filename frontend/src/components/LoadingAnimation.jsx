import React from 'react';
import { motion } from 'framer-motion';

export default function LoadingAnimation() {
  const dotVariants = {
    start: { y: 0 },
    end: { y: -15 }
  };

  const transition = {
    duration: 0.5,
    repeat: Infinity,
    repeatType: "reverse",
    ease: "easeInOut"
  };

  return (
    <motion.div
      className="loading-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="loading-content">
        <div className="spinner-container">
          <motion.div
            className="spinner"
            animate={{ rotate: 360 }}
            transition={{
              duration: 1,
              repeat: Infinity,
              ease: "linear"
            }}
          >
            <div className="spinner-circle"></div>
          </motion.div>
        </div>

        <div className="loading-text-container">
          <motion.p
            className="loading-text"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            Analyzing claim
          </motion.p>
          <div className="loading-dots">
            <motion.span
              className="dot"
              variants={dotVariants}
              initial="start"
              animate="end"
              transition={{ ...transition, delay: 0 }}
            >
              •
            </motion.span>
            <motion.span
              className="dot"
              variants={dotVariants}
              initial="start"
              animate="end"
              transition={{ ...transition, delay: 0.15 }}
            >
              •
            </motion.span>
            <motion.span
              className="dot"
              variants={dotVariants}
              initial="start"
              animate="end"
              transition={{ ...transition, delay: 0.3 }}
            >
              •
            </motion.span>
          </div>
        </div>

        <motion.div
          className="loading-steps"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <LoadingStep text="Structuring claim" delay={0} />
          <LoadingStep text="Researching sources" delay={0.8} />
          <LoadingStep text="Verifying facts" delay={1.6} />
          <LoadingStep text="Generating verdict" delay={2.4} />
        </motion.div>
      </div>
    </motion.div>
  );
}

function LoadingStep({ text, delay }) {
  return (
    <motion.div
      className="loading-step"
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: [0, 1, 0.4] }}
      transition={{
        duration: 3.2,
        delay,
        repeat: Infinity,
        ease: "easeInOut"
      }}
    >
      <motion.div
        className="step-indicator"
        initial={{ scale: 0 }}
        animate={{ scale: [0, 1.2, 1] }}
        transition={{
          duration: 0.5,
          delay,
          repeat: Infinity,
          repeatDelay: 2.7
        }}
      />
      <span className="step-text">{text}</span>
    </motion.div>
  );
}
