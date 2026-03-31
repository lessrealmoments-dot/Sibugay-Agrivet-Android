/**
 * TotpVerifyDialog — thin wrapper around AuthDialog (mode="totp").
 * Preserved for backward compatibility with all existing consumers.
 */
import AuthDialog from './AuthDialog';

export function TotpVerifyDialog({
  open,
  onOpenChange,
  onVerified,
  context = '',
  title = 'Admin Authorization Required',
}) {
  return (
    <AuthDialog
      open={open}
      onClose={() => onOpenChange(false)}
      mode="totp"
      context={context}
      title={title}
      onVerified={onVerified}
    />
  );
}
