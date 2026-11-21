// Line icons (24×24, 1.75 stroke, currentColor). Lucide-style shapes drawn inline: no icon dependency.
const P = {
  logo: '<path d="M3 15c2.4-1.9 4.6-1.9 7 0s4.6 1.9 7 0 3.4-1.5 4-1"/><path d="M3 19.5c2.4-1.9 4.6-1.9 7 0s4.6 1.9 7 0 3.4-1.5 4-1"/><path d="M12 3v9"/><path d="M9.5 5.5h5"/><path d="M10.5 8.5h3"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  video: '<path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
  droplet: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  play: '<path d="M7 4.5v15a1 1 0 0 0 1.5.86l12-7.5a1 1 0 0 0 0-1.72l-12-7.5A1 1 0 0 0 7 4.5Z"/>',
  pause: '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
  locate: '<circle cx="12" cy="12" r="7"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="1.5"/>',
  building: '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
  route: '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
  sparkles: '<path d="M9.9 14.5 8.5 20l-1.4-5.5L1.5 13l5.6-1.5L8.5 6l1.4 5.5 5.6 1.5z"/><path d="M19 3v4"/><path d="M21 5h-4"/>',
  gauge: '<path d="M12 3v18"/><path d="M12 7h4M12 11h3M12 15h4M12 19h3"/><path d="M4 16c1.5-1.2 3-1.2 4.5 0"/>',
  lock: '<rect width="16" height="10" x="4" y="11" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  overview: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
  compass: '<circle cx="12" cy="12" r="10"/><path d="m16.2 7.8-2.1 6.3-6.3 2.1 2.1-6.3z"/>',
  street: '<circle cx="12" cy="4.5" r="2"/><path d="M12 8v6M8.5 10.5 12 9l3.5 1.5M9.5 21l2.5-7 2.5 7"/>',
  ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  map: '<path d="M14.1 5.1 9.9 3.4a2 2 0 0 0-1.6 0L3.6 5.3A1 1 0 0 0 3 6.2v13.3a1 1 0 0 0 1.4.9l4-1.7a2 2 0 0 1 1.6 0l4.2 1.7a2 2 0 0 0 1.6 0l4.6-1.9a1 1 0 0 0 .6-.9V4.3a1 1 0 0 0-1.4-.9l-4 1.7a2 2 0 0 1-1.7 0Z"/><path d="M9 3.5v15M15 5.5v15"/>',
  key: '<path d="M4 6h16M4 12h10M4 18h6"/>',
  restart: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
};

export function icon(name, cls = '') {
  return `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ` +
    `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || ''}</svg>`;
}
