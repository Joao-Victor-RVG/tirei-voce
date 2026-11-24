import { api } from "@/api/client";

export type PushSupport = "supported" | "unsupported" | "needs-install";

export function pushSupport(): PushSupport {
  if (typeof window === "undefined") return "unsupported";
  const hasApis =
    "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (hasApis) return "supported";
  // No iPhone o push só existe com o app instalado na tela inicial (iOS 16.4+).
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  return ios ? "needs-install" : "unsupported";
}

export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator) || import.meta.env.MODE === "test") return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.getRegistration();
  return (await registration?.pushManager.getSubscription()) ?? null;
}

export async function enablePush(publicKey: string): Promise<void> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Permissão negada. Libere as notificações nas configurações do navegador.");
  }
  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    }));
  await api<void>("/push/subscriptions", { method: "POST", body: subscription.toJSON() });
}

export async function disablePush(): Promise<void> {
  const subscription = await currentSubscription();
  if (!subscription) return;
  await api<void>("/push/subscriptions", {
    method: "DELETE",
    query: { endpoint: subscription.endpoint },
  });
  await subscription.unsubscribe();
}
