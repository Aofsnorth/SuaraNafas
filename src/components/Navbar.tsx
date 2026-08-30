"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent } from "react";

const NAV_LINKS = [
  { href: "/#mengapa-penting", label: "Mengapa penting" },
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
  const actionLabel = isAnalyzePage ? "Beranda" : "Uji rekaman";

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
      <a className="skip-link" href="#konten-utama">
        Lewati ke konten utama
      </a>
      <span data-nav-sentinel aria-hidden="true" />
      <header className="site-header" data-scrolled={isScrolled ? "true" : "false"}>
        <nav className="site-nav" aria-label="Navigasi utama">
          <Link className="site-nav__wordmark" href="/" aria-label="Beranda SuaraNafas">
            <span className="wordmark-dot" aria-hidden="true" />
            SuaraNafas
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
              {actionLabel}
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
            <span>SuaraNafas</span>
            <button type="button" onClick={closeMenu} aria-label="Tutup menu navigasi">
              Tutup
            </button>
          </div>
          <nav className="mobile-navigation__links" aria-label="Navigasi seluler">
            {NAV_LINKS.map((link) => (
              <Link href={link.href} key={link.href} onClick={closeMenu}>
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </dialog>
    </>
  );
}
