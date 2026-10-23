import { useCallback, useEffect, useRef } from "react";
import { useMap } from "react-leaflet";

/**
 * Viewport controller shared by every district map in the app. Focusing a
 * district frames its bounds (capped zoom), clearing it refits the national
 * envelope, and the initial mount keeps whatever center/zoom the MapContainer
 * was configured with.
 *
 * The maps render inside collapsible tabs. Leaflet computes NaN centers when it
 * fits bounds in a zero-sized container, so view requests made while hidden are
 * parked on pendingRef and re-applied — after invalidateSize — once the
 * container is measurable again.
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
