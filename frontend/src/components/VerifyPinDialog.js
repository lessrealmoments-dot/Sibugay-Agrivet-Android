/**
 * VerifyPinDialog — thin wrapper around AuthDialog (mode="pin").
 * Preserved for backward compatibility with all existing consumers.
 */
import AuthDialog from './AuthDialog';

export default function VerifyPinDialog({ open, onClose, docType, docId, docLabel, onVerified }) {
  return (
    <AuthDialog
      open={open}
      onClose={onClose}
      mode="pin"
      docType={docType}
      docId={docId}
      docLabel={docLabel}
      onVerified={onVerified}
    />
  );
}
