import QRCode from "qrcode";

export async function listingQrSvg(url: string): Promise<string> {
  return QRCode.toString(url, {
    type: "svg",
    margin: 0,
    width: 128,
    color: { dark: "#18181b", light: "#ffffff" },
  });
}
