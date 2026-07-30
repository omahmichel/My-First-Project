import { useEffect, useRef, useState } from "react";

import "../../styles/sticky-table-scroll.css";

// Keeps a synchronized horizontal scrollbar visible while a wide table is on screen.
export default function StickyTableScroll({ children, className = "" }) {
  const contentRef = useRef(null);
  const scrollbarRef = useRef(null);
  const spacerRef = useRef(null);
  const frameRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const [barStyle, setBarStyle] = useState({ left: 0, width: 0 });

  useEffect(() => {
    const content = contentRef.current;
    const scrollbar = scrollbarRef.current;
    const spacer = spacerRef.current;

    if (!content || !scrollbar || !spacer) return undefined;

    function updateScrollbar() {
      window.cancelAnimationFrame(frameRef.current);

      frameRef.current = window.requestAnimationFrame(() => {
        const rect = content.getBoundingClientRect();
        const left = Math.max(0, rect.left);
        const right = Math.min(window.innerWidth, rect.right);
        const width = Math.max(0, right - left);
        const hasHorizontalOverflow =
          content.scrollWidth - content.clientWidth > 2;
        const tableIsVisible =
          rect.bottom > 52 &&
          rect.top < window.innerHeight - 12 &&
          width > 120;

        spacer.style.width = `${content.scrollWidth}px`;
        scrollbar.scrollLeft = content.scrollLeft;

        setBarStyle({ left, width });
        setVisible(hasHorizontalOverflow && tableIsVisible);
      });
    }

    const resizeObserver = new ResizeObserver(updateScrollbar);

    resizeObserver.observe(content);

    if (content.firstElementChild) {
      resizeObserver.observe(content.firstElementChild);
    }

    window.addEventListener("resize", updateScrollbar);
    window.addEventListener("scroll", updateScrollbar, { passive: true });

    updateScrollbar();

    return () => {
      window.cancelAnimationFrame(frameRef.current);
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateScrollbar);
      window.removeEventListener("scroll", updateScrollbar);
    };
  }, []);

  function syncFromTable() {
    if (scrollbarRef.current && contentRef.current) {
      scrollbarRef.current.scrollLeft = contentRef.current.scrollLeft;
    }
  }

  function syncFromStickyBar() {
    if (contentRef.current && scrollbarRef.current) {
      contentRef.current.scrollLeft = scrollbarRef.current.scrollLeft;
    }
  }

  const wrapperClassName = [
    "responsive-table-wrapper",
    "sticky-table-scroll-content",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <div
        ref={contentRef}
        className={wrapperClassName}
        onScroll={syncFromTable}
      >
        {children}
      </div>

      <div
        ref={scrollbarRef}
        className={`sticky-table-scroll-bar ${
          visible ? "sticky-table-scroll-bar-visible" : ""
        }`}
        style={{
          left: `${barStyle.left}px`,
          width: `${barStyle.width}px`,
        }}
        onScroll={syncFromStickyBar}
        aria-hidden="true"
      >
        <div ref={spacerRef} className="sticky-table-scroll-spacer" />
      </div>
    </>
  );
}
