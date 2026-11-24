/* Service worker do Tirei Você!: só notificações push e instalação (sem cache offline,
   para nunca servir uma versão velha do app). */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: "Tirei Você!", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Tirei Você!";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/badge-72.png",
      tag: data.tag,
      renotify: Boolean(data.tag),
      data: { url: data.url || "/groups" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/groups", self.location.origin);
  if (target.origin !== self.location.origin) return;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of windows) {
        if (new URL(client.url).origin === target.origin && "focus" in client) {
          await client.focus();
          return client.navigate(target.href);
        }
      }
      return self.clients.openWindow(target.href);
    })(),
  );
});
