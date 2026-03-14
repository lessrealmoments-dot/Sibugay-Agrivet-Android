import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { Copy, Check, FileText, Printer, X } from 'lucide-react';
import PrintEngine from '../lib/PrintEngine';
import { api } from '../contexts/AuthContext';

/**
 * Modal after transaction creation — shows reference number + print option.
 * Props:
 *   open, onClose, referenceNumber, type, title
 *   invoiceData: full invoice/PO object for printing
 *   businessInfo: from /settings/business-info
 */
export default function ReferenceNumberPrompt({ open, onClose, referenceNumber, type = "sale", title, invoiceData, businessInfo }) {
  const [copied, setCopied] = useState(false);
  const [printing, setPrinting] = useState(false);

  const typeLabel = {
    sale: 'Sales Receipt',
    po: 'Purchase Order',
    expense: 'Expense',
    invoice: 'Invoice',
  }[type] || 'Transaction';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(referenceNumber);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const el = document.createElement('textarea');
      el.value = referenceNumber;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handlePrint = async (format) => {
    if (!invoiceData) return;
    setPrinting(true);
    try {
      // Generate doc code for QR
      let docCode = '';
      const docTypeMap = { sale: 'invoice', po: 'purchase_order', invoice: 'invoice' };
      const docType = docTypeMap[type] || 'invoice';
      const docId = invoiceData.id;
      if (docId) {
        try {
          const res = await api.post('/doc/generate-code', { doc_type: docType, doc_id: docId });
          docCode = res.data?.code || '';
        } catch { /* print without QR */ }
      }

      const printType = PrintEngine.getDocType(invoiceData);
      PrintEngine.print({
        type: type === 'po' ? 'purchase_order' : printType,
        data: invoiceData,
        format,
        businessInfo: businessInfo || {},
        docCode,
      });
    } catch (e) {
      console.error('Print error:', e);
    }
    setPrinting(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md" data-testid="reference-number-prompt">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <FileText size={20} className="text-[#1A4D2E]" />
            {typeLabel} Created
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Big reference number display */}
          <div className="bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl p-5 text-center"
            data-testid="reference-number-display">
            <p className="font-mono text-2xl font-bold text-slate-800 tracking-wider select-all">
              {referenceNumber}
            </p>
            {title && <p className="text-sm text-slate-500 mt-1">{title}</p>}
          </div>

          {/* Print options */}
          {invoiceData && (
            <div className="space-y-2">
              <p className="text-sm text-slate-600 font-medium">Print this receipt?</p>
              <div className="flex gap-2">
                <Button
                  data-testid="print-full-page-btn"
                  variant="outline"
                  className="flex-1 h-11"
                  onClick={() => handlePrint('full_page')}
                  disabled={printing}
                >
                  <Printer size={16} className="mr-2" /> Full Page (8.5x11)
                </Button>
                <Button
                  data-testid="print-thermal-btn"
                  variant="outline"
                  className="flex-1 h-11"
                  onClick={() => handlePrint('thermal')}
                  disabled={printing}
                >
                  <Printer size={16} className="mr-2" /> Thermal (58mm)
                </Button>
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <Button
              data-testid="reference-copy-btn"
              variant="outline"
              className="flex-1"
              onClick={handleCopy}
            >
              {copied ? (
                <><Check size={16} className="mr-2 text-green-600" /> Copied!</>
              ) : (
                <><Copy size={16} className="mr-2" /> Copy Number</>
              )}
            </Button>
            <Button
              data-testid="reference-done-btn"
              className="flex-1 bg-[#1A4D2E] hover:bg-[#154025]"
              onClick={onClose}
            >
              Done
            </Button>
          </div>

          <p className="text-[11px] text-slate-400 text-center">
            This number is searchable — use Find Transaction (Ctrl+K) to look it up anytime
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
