document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.getElementById("mobileMenuButton");
  const navLinks = document.getElementById("navLinks");

  if (window.lucide) window.lucide.createIcons();

  if (!menuButton || !navLinks) return;

  menuButton.addEventListener("click", () => {
    const open = navLinks.classList.toggle("nav-links-open");
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.innerHTML = open ? '<i data-lucide="x"></i>' : '<i data-lucide="menu"></i>';
    if (window.lucide) window.lucide.createIcons();
  });

  navLinks.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      navLinks.classList.remove("nav-links-open");
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.innerHTML = '<i data-lucide="menu"></i>';
      if (window.lucide) window.lucide.createIcons();
    });
  });
});
