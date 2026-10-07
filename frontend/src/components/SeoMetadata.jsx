import { useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";
import { applyPageMetadata } from "../utils/seo";

export default function SeoMetadata() {
  const { pathname } = useLocation();
  useLayoutEffect(() => { applyPageMetadata(pathname); }, [pathname]);
  return null;
}
