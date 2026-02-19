import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export const formatPHP = (amount) => {
  return `₱${(amount || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const formatQty = (qty, unit) => {
  const q = qty || 0;
  return `${q % 1 === 0 ? q : q.toFixed(2)} ${unit || ''}`.trim();
};
