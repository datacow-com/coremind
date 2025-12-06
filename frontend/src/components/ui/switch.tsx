import * as React from "react";

export interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Switch: React.FC<SwitchProps> = (props) => {
  return (
    <label className="inline-flex cursor-pointer items-center space-x-2">
      <input type="checkbox" className="peer hidden" {...props} />
      <span className="h-4 w-8 rounded-full bg-input peer-checked:bg-primary transition-colors relative">
        <span className="absolute left-0 top-0 h-4 w-4 rounded-full bg-white shadow peer-checked:left-4 transition-all" />
      </span>
    </label>
  );
};
