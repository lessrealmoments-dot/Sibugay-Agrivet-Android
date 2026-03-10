import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Button } from '../components/ui/button';
import { Copy, Check, FileText } from 'lucide-react';

/**
 * Modal that prompts the user to write the reference number on their original receipt.
 * Shows after any transaction creation (sale, PO, expense).
 *
 * Props:
 *   open: boolean
 *   onClose: () => void
 *   referenceNumber: string (e.g., "SI-MN-001042")
 *   type: "sale" | "po" | "expense" | "invoice"
 *   title: optional label (e.g., "Walk-in" or vendor name)
 */
export default function ReferenceNumberPrompt({ open, onClose, referenceNumber, type = "sale", title }) {
  const [copied, setCopied] = useState(false);

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
      // Fallback
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
          <p className="text-sm text-slate-600">
            Write this reference number on your original receipt for easy tracking:
          </p>

          {/* Big reference number display */}
          <div className="bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl p-5 text-center"
            data-testid="reference-number-display">
            <p className="font-mono text-2xl font-bold text-slate-800 tracking-wider select-all">
              {referenceNumber}
            </p>
            {title && (
              <p className="text-sm text-slate-500 mt-1">{title}</p>
            )}
          </div>

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
