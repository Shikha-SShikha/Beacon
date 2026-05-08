interface Props {
  size?: "sm" | "md" | "lg";
  variant?: "dark" | "light";
}

const CONFIG = {
  sm: { h: 32 },
  md: { h: 40 },
  lg: { h: 56 },
};

export default function BeaconLogo({ size = "md", variant = "dark" }: Props) {
  const c = CONFIG[size];

  return (
    <img
      src="/beacon-logo.svg"
      alt="Beacon"
      style={{
        height: c.h,
        objectFit: "contain",
        ...(variant === "light" ? { filter: "brightness(0) invert(1)" } : {}),
      }}
      className="select-none"
    />
  );
}
