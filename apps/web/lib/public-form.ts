export function scrollPublicFieldIntoView(event: { currentTarget: HTMLElement }) {
  const target = event.currentTarget;
  window.setTimeout(() => {
    target.scrollIntoView({ block: "center", behavior: "smooth" });
  }, 300);
}
