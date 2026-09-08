type PrintPhotoProps = {
  src: string;
  alt?: string;
  variant: "cover" | "thumb";
};

export function PrintPhoto({ src, alt = "", variant }: PrintPhotoProps) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- print layout needs native img sizing
    <img
      src={src}
      alt={alt}
      className={
        variant === "cover" ? "print-photo print-photo--cover" : "print-photo print-photo--thumb"
      }
    />
  );
}
