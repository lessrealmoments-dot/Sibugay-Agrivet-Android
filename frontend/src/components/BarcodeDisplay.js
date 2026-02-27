import { useEffect, useRef } from 'react';
import JsBarcode from 'jsbarcode';

export function BarcodeDisplay({ value, width = 1.5, height = 40, displayValue = true, fontSize = 12, className = '' }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!value || !svgRef.current) return;
    try {
      JsBarcode(svgRef.current, value, {
        format: 'CODE128',
        width,
        height,
        displayValue,
        fontSize,
        margin: 4,
        textMargin: 2,
      });
    } catch (e) {
      console.warn('Barcode render error:', e);
    }
  }, [value, width, height, displayValue, fontSize]);

  if (!value) return null;
  return <svg ref={svgRef} className={className} />;
}
