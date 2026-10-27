import { useCallback, useEffect, useRef } from "react";
import { useMap } from "react-leaflet";

/**
 * Viewport controller for the district maps: focusing a district frames its
 * bounds, clearing it refits the national envelope. Leaflet computes NaN
 * centers in zero-sized containers, so view requests made while the tab is
 * hidden park on pendingRef and re-apply after invalidateSize.
 */
export default function MapFocus({
  selectedDistrict = "",
  getDistrictBounds,
  nationalBounds,
  maxZoom,
  focusPadding = [36, 36],
  nationalPadding = [12, 12],
}) {
  const map = useMap();
  const previous = useRef(undefined);
  const pendingRef = useRef(null);

  const frame = useCallback(
    (district) => {
      let tapped = false;
      if (district) {
        const bounds = getDistrictBounds(district);
        if (bounds) {
          try {
            if (bounds.isValid()) {
              map.fitBounds(bounds, { padding: focusPadding, maxZoom });
              tapped = true;
            }
          } catch {
            tapped = false;
          }
        }
      }
      if (!tapped) {
        try {
          map.fitBounds(nationalBounds, { padding: nationalPadding });
        } catch {
          /* hidden or torn-down container — the observer below retries */
        }
      }
    },
    [map, getDistrictBounds, nationalBounds, maxZoom, focusPadding, nationalPadding],
  );

  useEffect(() => {
    if (!map) return;
    const measurable = () => {
      const el = map.getContainer();
      return !!el && el.clientWidth > 0 && el.clientHeight > 0;
    };

    if (previous.current === undefined) {
      previous.current = selectedDistrict;
      return;
    }
    previous.current = selectedDistrict;
    pendingRef.current = selectedDistrict;
    if (!measurable()) return;
    pendingRef.current = null;
    frame(selectedDistrict);
  }, [map, selectedDistrict, frame]);

  useEffect(() => {
    if (!map) return undefined;
    const observer = new ResizeObserver(() => {
      const el = map.getContainer();
      if (!el || el.clientWidth <= 0 || el.clientHeight <= 0) return;
      map.invalidateSize();
      if (pendingRef.current == null) return;
      const district = pendingRef.current;
      pendingRef.current = null;
      frame(district);
    });
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map, frame]);

  return null;
}
