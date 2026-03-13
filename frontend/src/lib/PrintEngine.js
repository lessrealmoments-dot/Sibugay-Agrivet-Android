/**
 * PrintEngine — Generates print-ready HTML for thermal (58mm) and full-page (8.5x11) documents.
 * Document types: Order Slip, Trust Receipt, PO, etc.
 * Usage: PrintEngine.print({ type, data, format, businessInfo })
 */

const THERMAL_WIDTH = '58mm';
const FULL_PAGE_WIDTH = '8.5in';

function formatPHP(v) {
  const n = parseFloat(v) || 0;
  return `₱${n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(d) {
  if (!d) return '';
  try { return new Date(d).toLocaleDateString('en-PH', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return d; }
}

function fmtDateTime(d) {
  if (!d) return '';
  try { return new Date(d).toLocaleString('en-PH', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return d; }
}

// ── Thermal Receipt CSS ─────────────────────────────────────────────────────
const thermalCSS = `
  @page { size: 58mm auto; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Courier New', monospace; font-size: 10px; line-height: 1.3; width: 58mm; padding: 2mm; color: #000; }
  .header { text-align: center; margin-bottom: 4px; }
  .header .biz-name { font-size: 12px; font-weight: bold; text-transform: uppercase; }
  .header .biz-detail { font-size: 8px; }
  .doc-title { text-align: center; font-size: 11px; font-weight: bold; border-top: 1px dashed #000; border-bottom: 1px dashed #000; padding: 3px 0; margin: 4px 0; letter-spacing: 1px; }
  .meta-row { display: flex; justify-content: space-between; font-size: 9px; }
  .meta-row .label { color: #444; }
  .sep { border-top: 1px dashed #000; margin: 3px 0; }
  .items-table { width: 100%; font-size: 9px; }
  .items-table td { padding: 1px 0; vertical-align: top; }
  .items-table .item-name { font-weight: bold; }
  .items-table .item-detail { padding-left: 8px; font-size: 8px; color: #333; }
  .items-table .item-total { text-align: right; font-weight: bold; }
  .totals { margin-top: 4px; }
  .totals .row { display: flex; justify-content: space-between; font-size: 9px; padding: 1px 0; }
  .totals .grand { font-size: 12px; font-weight: bold; border-top: 1px solid #000; padding-top: 3px; margin-top: 2px; }
  .payment-info { margin-top: 4px; font-size: 9px; }
  .trust-terms { margin-top: 6px; font-size: 7px; line-height: 1.2; border-top: 1px dashed #000; padding-top: 4px; }
  .trust-terms .terms-title { font-weight: bold; font-size: 8px; margin-bottom: 2px; text-align: center; }
  .signature-line { margin-top: 16px; text-align: center; }
  .signature-line .line { border-top: 1px solid #000; width: 70%; margin: 0 auto; }
  .signature-line .sig-label { font-size: 7px; color: #666; margin-top: 2px; }
  .footer { text-align: center; font-size: 7px; color: #666; margin-top: 6px; border-top: 1px dashed #000; padding-top: 4px; }
  @media print { body { width: 58mm; } }
`;

// ── Full Page CSS ───────────────────────────────────────────────────────────
const fullPageCSS = `
  @page { size: 8.5in 11in; margin: 0.5in; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; line-height: 1.4; color: #222; max-width: 7.5in; }
  .header { text-align: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #1A4D2E; }
  .header .biz-name { font-size: 18px; font-weight: bold; color: #1A4D2E; }
  .header .biz-detail { font-size: 10px; color: #555; }
  .doc-title { font-size: 16px; font-weight: bold; text-align: center; margin: 12px 0; color: #1A4D2E; letter-spacing: 2px; text-transform: uppercase; }
  .meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 20px; margin: 10px 0; font-size: 10px; }
  .meta-grid .label { color: #666; }
  .meta-grid .value { font-weight: bold; }
  .items-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10px; }
  .items-table th { background: #f1f5f0; border: 1px solid #ddd; padding: 6px 8px; text-align: left; font-size: 9px; text-transform: uppercase; color: #555; }
  .items-table td { border: 1px solid #eee; padding: 5px 8px; }
  .items-table .text-right { text-align: right; }
  .items-table .text-center { text-align: center; }
  .items-table tfoot td { font-weight: bold; background: #fafafa; }
  .totals-section { display: flex; justify-content: flex-end; margin: 12px 0; }
  .totals-box { width: 280px; }
  .totals-box .row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 10px; }
  .totals-box .grand { font-size: 14px; font-weight: bold; border-top: 2px solid #1A4D2E; padding-top: 6px; margin-top: 4px; color: #1A4D2E; }
  .payment-info { margin: 12px 0; font-size: 10px; padding: 8px; background: #f9f9f9; border-radius: 4px; }
  .trust-terms { margin: 16px 0; font-size: 9px; line-height: 1.4; border: 1px solid #ddd; padding: 10px; border-radius: 4px; }
  .trust-terms .terms-title { font-weight: bold; font-size: 10px; margin-bottom: 4px; text-transform: uppercase; }
  .signature-section { display: flex; justify-content: space-between; margin-top: 40px; padding-top: 10px; }
  .signature-block { text-align: center; width: 200px; }
  .signature-block .line { border-top: 1px solid #000; margin-bottom: 4px; }
  .signature-block .sig-label { font-size: 9px; color: #666; }
  .footer { text-align: center; font-size: 8px; color: #999; margin-top: 20px; border-top: 1px solid #eee; padding-top: 8px; }
  @media print { body { max-width: none; } }
`;

// ── Build header HTML ───────────────────────────────────────────────────────
function buildHeader(biz) {
  const parts = [];
  parts.push(`<div class="biz-name">${biz.business_name || 'Business Name'}</div>`);
  if (biz.address) parts.push(`<div class="biz-detail">${biz.address}</div>`);
  if (biz.phone) parts.push(`<div class="biz-detail">${biz.phone}</div>`);
  if (biz.tin) parts.push(`<div class="biz-detail">TIN: ${biz.tin}</div>`);
  return `<div class="header">${parts.join('')}</div>`;
}

// ── Items table ─────────────────────────────────────────────────────────────
function buildItemsThermal(items) {
  let html = '<table class="items-table">';
  for (const item of items) {
    const qty = parseFloat(item.quantity) || 0;
    const rate = parseFloat(item.rate || item.unit_price || item.price) || 0;
    const total = parseFloat(item.total) || (qty * rate);
    html += `<tr><td class="item-name" colspan="2">${item.product_name || item.description || ''}</td></tr>`;
    html += `<tr><td class="item-detail">${qty} x ${formatPHP(rate)}</td><td class="item-total">${formatPHP(total)}</td></tr>`;
  }
  html += '</table>';
  return html;
}

function buildItemsFullPage(items) {
  let html = '<table class="items-table"><thead><tr>';
  html += '<th>#</th><th>Item</th><th class="text-center">Qty</th><th class="text-right">Price</th><th class="text-right">Discount</th><th class="text-right">Total</th>';
  html += '</tr></thead><tbody>';
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const qty = parseFloat(item.quantity) || 0;
    const rate = parseFloat(item.rate || item.unit_price || item.price) || 0;
    const disc = parseFloat(item.discount_amount) || 0;
    const total = parseFloat(item.total) || (qty * rate - disc);
    html += `<tr>`;
    html += `<td class="text-center">${i + 1}</td>`;
    html += `<td>${item.product_name || item.description || ''}</td>`;
    html += `<td class="text-center">${qty}</td>`;
    html += `<td class="text-right">${formatPHP(rate)}</td>`;
    html += `<td class="text-right">${disc > 0 ? formatPHP(disc) : '-'}</td>`;
    html += `<td class="text-right">${formatPHP(total)}</td>`;
    html += `</tr>`;
  }
  html += '</tbody></table>';
  return html;
}

// ── Order Slip ──────────────────────────────────────────────────────────────
function orderSlipThermal(data, biz) {
  const inv = data;
  let html = buildHeader(biz);
  html += `<div class="doc-title">ORDER SLIP</div>`;
  html += `<div class="meta-row"><span class="label">No:</span><span>${inv.invoice_number || ''}</span></div>`;
  html += `<div class="meta-row"><span class="label">Date:</span><span>${fmtDateTime(inv.created_at || inv.order_date)}</span></div>`;
  if (inv.customer_name && inv.customer_name !== 'Walk-in') {
    html += `<div class="meta-row"><span class="label">Customer:</span><span>${inv.customer_name}</span></div>`;
  }
  html += `<div class="meta-row"><span class="label">Cashier:</span><span>${inv.cashier_name || ''}</span></div>`;
  html += '<div class="sep"></div>';
  html += buildItemsThermal(inv.items || []);
  html += '<div class="sep"></div>';
  html += '<div class="totals">';
  html += `<div class="row"><span>Subtotal</span><span>${formatPHP(inv.subtotal)}</span></div>`;
  if (inv.overall_discount > 0) html += `<div class="row"><span>Discount</span><span>-${formatPHP(inv.overall_discount)}</span></div>`;
  if (inv.freight > 0) html += `<div class="row"><span>Freight</span><span>${formatPHP(inv.freight)}</span></div>`;
  html += `<div class="row grand"><span>TOTAL</span><span>${formatPHP(inv.grand_total)}</span></div>`;
  html += '</div>';
  html += '<div class="payment-info">';
  html += `<div class="meta-row"><span class="label">Payment:</span><span>${inv.payment_method || 'Cash'}</span></div>`;
  if (inv.amount_paid > 0 && inv.payment_type !== 'credit') {
    html += `<div class="meta-row"><span class="label">Paid:</span><span>${formatPHP(inv.amount_paid)}</span></div>`;
    const change = (inv.amount_paid || 0) - (inv.grand_total || 0);
    if (change > 0) html += `<div class="meta-row"><span class="label">Change:</span><span>${formatPHP(change)}</span></div>`;
  }
  html += '</div>';
  html += `<div class="footer">${biz.receipt_footer || 'This is not an official receipt.'}<br>Thank you!</div>`;
  return html;
}

function orderSlipFullPage(data, biz) {
  const inv = data;
  let html = buildHeader(biz);
  html += `<div class="doc-title">Order Slip</div>`;
  html += '<div class="meta-grid">';
  html += `<div><span class="label">Slip No: </span><span class="value">${inv.invoice_number || ''}</span></div>`;
  html += `<div><span class="label">Date: </span><span class="value">${fmtDateTime(inv.created_at || inv.order_date)}</span></div>`;
  html += `<div><span class="label">Customer: </span><span class="value">${inv.customer_name || 'Walk-in'}</span></div>`;
  html += `<div><span class="label">Cashier: </span><span class="value">${inv.cashier_name || ''}</span></div>`;
  if (inv.payment_method) html += `<div><span class="label">Payment: </span><span class="value">${inv.payment_method}</span></div>`;
  html += '</div>';
  html += buildItemsFullPage(inv.items || []);
  html += '<div class="totals-section"><div class="totals-box">';
  html += `<div class="row"><span>Subtotal</span><span>${formatPHP(inv.subtotal)}</span></div>`;
  if (inv.overall_discount > 0) html += `<div class="row"><span>Discount</span><span>-${formatPHP(inv.overall_discount)}</span></div>`;
  if (inv.freight > 0) html += `<div class="row"><span>Freight</span><span>${formatPHP(inv.freight)}</span></div>`;
  html += `<div class="row grand"><span>TOTAL</span><span>${formatPHP(inv.grand_total)}</span></div>`;
  if (inv.amount_paid > 0) html += `<div class="row"><span>Amount Paid</span><span>${formatPHP(inv.amount_paid)}</span></div>`;
  html += '</div></div>';
  html += `<div class="footer">${biz.receipt_footer || 'This is not an official receipt.'}</div>`;
  return html;
}

// ── Trust Receipt ───────────────────────────────────────────────────────────
function trustReceiptThermal(data, biz) {
  const inv = data;
  let html = buildHeader(biz);
  html += `<div class="doc-title">TRUST RECEIPT</div>`;
  html += `<div class="meta-row"><span class="label">No:</span><span>${inv.invoice_number || ''}</span></div>`;
  html += `<div class="meta-row"><span class="label">Date:</span><span>${fmtDate(inv.order_date || inv.created_at)}</span></div>`;
  html += `<div class="meta-row"><span class="label">Customer:</span><span>${inv.customer_name || ''}</span></div>`;
  if (inv.due_date) html += `<div class="meta-row"><span class="label">Due:</span><span>${fmtDate(inv.due_date)}</span></div>`;
  if (inv.terms && inv.terms !== 'COD') html += `<div class="meta-row"><span class="label">Terms:</span><span>${inv.terms}</span></div>`;
  html += `<div class="meta-row"><span class="label">Cashier:</span><span>${inv.cashier_name || ''}</span></div>`;
  html += '<div class="sep"></div>';
  html += buildItemsThermal(inv.items || []);
  html += '<div class="sep"></div>';
  html += '<div class="totals">';
  html += `<div class="row"><span>Subtotal</span><span>${formatPHP(inv.subtotal)}</span></div>`;
  if (inv.overall_discount > 0) html += `<div class="row"><span>Discount</span><span>-${formatPHP(inv.overall_discount)}</span></div>`;
  html += `<div class="row grand"><span>TOTAL</span><span>${formatPHP(inv.grand_total)}</span></div>`;
  if (inv.amount_paid > 0) html += `<div class="row"><span>Paid</span><span>${formatPHP(inv.amount_paid)}</span></div>`;
  if (inv.balance > 0) html += `<div class="row" style="font-weight:bold;color:#c00"><span>BALANCE DUE</span><span>${formatPHP(inv.balance)}</span></div>`;
  if (inv.interest_rate > 0) html += `<div class="row" style="font-size:8px"><span>Interest Rate</span><span>${inv.interest_rate}%/mo</span></div>`;
  html += '</div>';
  // Trust terms
  const terms = (biz.trust_receipt_terms || '').replace('{business_name}', biz.business_name || '');
  if (terms) {
    html += `<div class="trust-terms"><div class="terms-title">TERMS AND CONDITIONS</div>${terms}</div>`;
  }
  html += '<div class="signature-line"><div style="margin-top:20px"></div><div class="line"></div><div class="sig-label">Customer Signature</div></div>';
  html += `<div class="footer">${fmtDate(inv.order_date || inv.created_at)}</div>`;
  return html;
}

function trustReceiptFullPage(data, biz) {
  const inv = data;
  let html = buildHeader(biz);
  html += `<div class="doc-title">Trust Receipt</div>`;
  html += '<div class="meta-grid">';
  html += `<div><span class="label">Receipt No: </span><span class="value">${inv.invoice_number || ''}</span></div>`;
  html += `<div><span class="label">Date: </span><span class="value">${fmtDate(inv.order_date || inv.created_at)}</span></div>`;
  html += `<div><span class="label">Customer: </span><span class="value">${inv.customer_name || ''}</span></div>`;
  if (inv.due_date) html += `<div><span class="label">Due Date: </span><span class="value">${fmtDate(inv.due_date)}</span></div>`;
  if (inv.terms && inv.terms !== 'COD') html += `<div><span class="label">Terms: </span><span class="value">${inv.terms}</span></div>`;
  html += `<div><span class="label">Cashier: </span><span class="value">${inv.cashier_name || ''}</span></div>`;
  if (inv.customer_address) html += `<div><span class="label">Address: </span><span class="value">${inv.customer_address}</span></div>`;
  if (inv.customer_phone) html += `<div><span class="label">Phone: </span><span class="value">${inv.customer_phone}</span></div>`;
  html += '</div>';
  html += buildItemsFullPage(inv.items || []);
  html += '<div class="totals-section"><div class="totals-box">';
  html += `<div class="row"><span>Subtotal</span><span>${formatPHP(inv.subtotal)}</span></div>`;
  if (inv.overall_discount > 0) html += `<div class="row"><span>Discount</span><span>-${formatPHP(inv.overall_discount)}</span></div>`;
  if (inv.freight > 0) html += `<div class="row"><span>Freight</span><span>${formatPHP(inv.freight)}</span></div>`;
  html += `<div class="row grand"><span>TOTAL</span><span>${formatPHP(inv.grand_total)}</span></div>`;
  if (inv.amount_paid > 0) html += `<div class="row"><span>Amount Paid</span><span>${formatPHP(inv.amount_paid)}</span></div>`;
  if (inv.balance > 0) html += `<div class="row" style="color:#c00;font-weight:bold"><span>Balance Due</span><span>${formatPHP(inv.balance)}</span></div>`;
  if (inv.interest_rate > 0) html += `<div class="row" style="font-size:9px"><span>Interest Rate</span><span>${inv.interest_rate}% per month</span></div>`;
  html += '</div></div>';
  // Trust terms
  const terms = (biz.trust_receipt_terms || '').replace('{business_name}', biz.business_name || '');
  if (terms) {
    html += `<div class="trust-terms"><div class="terms-title">TERMS AND CONDITIONS</div><p>${terms}</p></div>`;
  }
  html += '<div class="signature-section">';
  html += '<div class="signature-block"><div class="line"></div><div class="sig-label">Trustor (Seller)</div></div>';
  html += '<div class="signature-block"><div class="line"></div><div class="sig-label">Trustee (Buyer) Signature Over Printed Name</div></div>';
  html += '</div>';
  return html;
}

// ── Print function ──────────────────────────────────────────────────────────
const PrintEngine = {
  /**
   * @param {object} opts
   * @param {'order_slip'|'trust_receipt'} opts.type
   * @param {object} opts.data - Invoice/PO data
   * @param {'thermal'|'full_page'} opts.format
   * @param {object} opts.businessInfo - From /settings/business-info
   */
  print({ type, data, format = 'thermal', businessInfo = {} }) {
    const css = format === 'thermal' ? thermalCSS : fullPageCSS;
    let body = '';

    switch (type) {
      case 'order_slip':
        body = format === 'thermal' ? orderSlipThermal(data, businessInfo) : orderSlipFullPage(data, businessInfo);
        break;
      case 'trust_receipt':
        body = format === 'thermal' ? trustReceiptThermal(data, businessInfo) : trustReceiptFullPage(data, businessInfo);
        break;
      default:
        body = format === 'thermal' ? orderSlipThermal(data, businessInfo) : orderSlipFullPage(data, businessInfo);
    }

    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Print</title><style>${css}</style></head><body>${body}</body></html>`;
    const win = window.open('', '_blank', 'width=400,height=600');
    if (!win) { alert('Please allow popups to print'); return; }
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); }, 300);
  },

  // Helper to determine doc type from invoice data
  getDocType(invoice) {
    if (!invoice) return 'order_slip';
    const pt = invoice.payment_type || '';
    const balance = parseFloat(invoice.balance) || 0;
    if (pt === 'credit' || pt === 'partial' || (balance > 0 && invoice.status !== 'paid')) {
      return 'trust_receipt';
    }
    return 'order_slip';
  },
};

export default PrintEngine;
