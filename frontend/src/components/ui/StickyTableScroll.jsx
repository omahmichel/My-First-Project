import { useEffect, useRef, useState } from "react";

import "../../styles/sticky-table-scroll.css";

// Keeps wide application tables horizontally synchronized and freezes their
// column headers below the app topbar while the user scrolls through records.
export default function StickyTableScroll({ children, className = "" }) {
  const contentRef = useRef(null);
  const scrollbarRef = useRef(null);
  const spacerRef = useRef(null);
  const frozenHeaderRef = useRef(null);
  const frozenSourceTableRef = useRef(null);
  const frozenSignatureRef = useRef("");
  const frameRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const [barStyle, setBarStyle] = useState({ left: 0, width: 0 });
  const [frozenVisible, setFrozenVisible] = useState(false);
  const [frozenStyle, setFrozenStyle] = useState({
    left: 0,
    top: 0,
    width: 0,
  });

  function syncFrozenHeader(content = contentRef.current) {
    const frozen = frozenHeaderRef.current;
    const table = content?.querySelector("table");
    const thead = table?.querySelector("thead");

    if (!content || !frozen || !table || !thead) {
      setFrozenVisible(false);
      return;
    }

    const contentRect = content.getBoundingClientRect();
    const tableRect = table.getBoundingClientRect();
    const headRect = thead.getBoundingClientRect();
    const topbar = document.querySelector(".app-topbar");
    const topbarBottom = topbar
      ? Math.max(0, topbar.getBoundingClientRect().bottom)
      : 0;
    const left = Math.max(0, contentRect.left);
    const right = Math.min(window.innerWidth, contentRect.right);
    const width = Math.max(0, right - left);
    const shouldFreeze =
      headRect.top <= topbarBottom &&
      tableRect.bottom > topbarBottom + headRect.height &&
      width > 120;

    setFrozenStyle({ left, top: topbarBottom, width });
    setFrozenVisible(shouldFreeze);

    const signature = thead.innerHTML;
    if (
      frozenSourceTableRef.current !== table ||
      frozenSignatureRef.current !== signature ||
      !frozen.firstElementChild
    ) {
      frozen.replaceChildren();

      const clonedTable = table.cloneNode(false);
      const clonedHead = thead.cloneNode(true);

      clonedTable.removeAttribute("id");
      clonedTable.setAttribute("aria-hidden", "true");
      clonedTable.appendChild(clonedHead);
      frozen.appendChild(clonedTable);

      frozenSourceTableRef.current = table;
      frozenSignatureRef.current = signature;
    }

    const clonedTable = frozen.querySelector("table");
    const sourceCells = thead.querySelectorAll("th");
    const clonedCells = clonedTable?.querySelectorAll("th") ?? [];

    sourceCells.forEach((cell, index) => {
      const clonedCell = clonedCells[index];
      if (!clonedCell) return;

      const widthPx = cell.getBoundingClientRect().width;
      const computed = window.getComputedStyle(cell);

      clonedCell.style.boxSizing = "border-box";
      clonedCell.style.width = `${widthPx}px`;
      clonedCell.style.minWidth = `${widthPx}px`;
      clonedCell.style.maxWidth = `${widthPx}px`;
      clonedCell.style.backgroundColor = computed.backgroundColor;
      clonedCell.style.color = computed.color;
      clonedCell.style.padding = computed.padding;
      clonedCell.style.font = computed.font;
      clonedCell.style.fontWeight = computed.fontWeight;
      clonedCell.style.letterSpacing = computed.letterSpacing;
      clonedCell.style.textAlign = computed.textAlign;
      clonedCell.style.verticalAlign = computed.verticalAlign;
      clonedCell.style.borderBottom = computed.borderBottom;
    });

    if (clonedTable) {
      clonedTable.style.width = `${tableRect.width}px`;
      clonedTable.style.minWidth = `${tableRect.width}px`;
      clonedTable.style.transform = `translateX(${
        contentRect.left - left - content.scrollLeft
      }px)`;
    }
  }

  useEffect(() => {
    const content = contentRef.current;
    const scrollbar = scrollbarRef.current;
    const spacer = spacerRef.current;

    if (!content || !scrollbar || !spacer) return undefined;

    function updateLayout() {
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
        syncFrozenHeader(content);
      });
    }

    const resizeObserver = new ResizeObserver(updateLayout);

    resizeObserver.observe(content);

    if (content.firstElementChild) {
      resizeObserver.observe(content.firstElementChild);
    }

    window.addEventListener("resize", updateLayout);
    window.addEventListener("scroll", updateLayout, { passive: true });

    updateLayout();

    return () => {
      window.cancelAnimationFrame(frameRef.current);
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateLayout);
      window.removeEventListener("scroll", updateLayout);
    };
  }, []);

  function syncFromTable() {
    if (scrollbarRef.current && contentRef.current) {
      scrollbarRef.current.scrollLeft = contentRef.current.scrollLeft;
      syncFrozenHeader(contentRef.current);
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

  const frozenClassName = [
    "sticky-table-frozen-header",
    frozenVisible ? "sticky-table-frozen-header-visible" : "",
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
        ref={frozenHeaderRef}
        className={frozenClassName}
        style={{
          left: `${frozenStyle.left}px`,
          top: `${frozenStyle.top}px`,
          width: `${frozenStyle.width}px`,
        }}
        aria-hidden="true"
      />

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
