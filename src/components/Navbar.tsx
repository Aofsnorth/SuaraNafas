"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent } from "react";

const NAV_LINKS = [
  { href: "/#cara-kerja", label: "Cara kerja" },
  { href: "/#sains", label: "Sains" },
  { href: "/#faq", label: "FAQ" },
] as const;

export function Navbar() {
  const pathname = usePathname();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const isAnalyzePage = pathname === "/analyze";
  const actionHref = isAnalyzePage ? "/" : "/analyze";
  const actionLabel = isAnalyzePage ? "Beranda" : "Mulai deteksi";
  const mobileActionLabel = isAnalyzePage ? "Beranda" : "Mulai";

  useEffect(() => {
    const sentinel = document.querySelector("[data-nav-sentinel]");
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => setIsScrolled(!entry.isIntersecting),
      { threshold: 0 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  const openMenu = () => {
    dialogRef.current?.showModal();
    setIsMenuOpen(true);
  };

  const closeMenu = () => {
    dialogRef.current?.close();
  };

  const handleDialogClose = () => {
    setIsMenuOpen(false);
    triggerRef.current?.focus();
  };

  const handleBackdropClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === dialogRef.current) closeMenu();
  };

  return (
    <>
      <span data-nav-sentinel className="nav-sentinel" aria-hidden="true" />
      <header className="site-header" data-scrolled={isScrolled ? "true" : "false"}>
        <nav className="site-nav" aria-label="Navigasi utama">
          <Link className="site-nav__wordmark" href="/" aria-label="Beranda Garuda Hacks 7.0">
            <span className="site-nav__wordmark-label site-nav__wordmark-label--desktop">
              Garuda Hacks 7.0
            </span>
            <span className="site-nav__wordmark-label site-nav__wordmark-label--mobile">
              Garuda Hacks 7.0
            </span>
          </Link>

          <div className="site-nav__links">
            {NAV_LINKS.map((link) => (
              <Link href={link.href} key={link.href}>
                {link.label}
              </Link>
            ))}
          </div>

          <div className="site-nav__actions">
            <Link className="site-nav__cta" href={actionHref}>
              <span className="site-nav__cta-label site-nav__cta-label--desktop">
                {actionLabel}
              </span>
              <span className="site-nav__cta-label site-nav__cta-label--mobile">
                {mobileActionLabel}
              </span>
            </Link>
            <button
              ref={triggerRef}
              type="button"
              className="site-nav__menu-trigger"
              aria-controls="mobile-navigation"
              aria-expanded={isMenuOpen}
              aria-label="Buka menu navigasi"
              onClick={openMenu}
            >
              Menu
            </button>
          </div>
        </nav>
      </header>

      <dialog
        ref={dialogRef}
        id="mobile-navigation"
        className="mobile-navigation"
        onClick={handleBackdropClick}
        onClose={handleDialogClose}
      >
        <div className="mobile-navigation__panel">
          <div className="mobile-navigation__topline">
            <span>Garuda Hacks 7.0</span>
            <button type="button" onClick={closeMenu} aria-label="Tutup menu navigasi">
              Tutup
            </button>
          </div>
          <div className="mobile-navigation__links">
            {NAV_LINKS.map((link) => (
              <Link href={link.href} key={link.href} onClick={closeMenu}>
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </dialog>
    </>
  );
}
