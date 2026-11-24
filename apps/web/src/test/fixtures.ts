import type { Group, Me } from "@/api/types";

export const ME: Me = {
  id: "u1",
  name: "Ana",
  email: "ana@example.com",
  email_verified: true,
  avatar_url: null,
  shirt_size: null,
  shoe_size: null,
  has_password: true,
  has_google: false,
  email_reminders: true,
};

export const THEMES = [
  { slug: "amigo-secreto", display_name: "Amigo Secreto", emoji: "🎁", description: "O clássico." },
  {
    slug: "amigo-da-onca",
    display_name: "Amigo da Onça",
    emoji: "🐆",
    description: "Presente duvidoso.",
  },
];

export function group(overrides: Partial<Group> = {}): Group {
  return {
    id: "g1",
    title: "Natal da Família",
    display_name: "Amigo Secreto",
    custom_name: null,
    description: null,
    theme: THEMES[0]!,
    min_value_cents: 5000,
    max_value_cents: 10000,
    event_at: "2099-12-24T23:00:00Z",
    event_location: "Casa da vó",
    event_maps_url: null,
    join_deadline_at: null,
    wishlist_deadline_at: null,
    status: "OPEN",
    invite_code: "abcdefghijkl",
    max_participants: 100,
    prefer_single_cycle: true,
    owner: { id: "u1", name: "Ana", avatar_url: null },
    my_role: "owner",
    my_participant_id: "p1",
    participant_count: 4,
    created_at: "2026-11-01T00:00:00Z",
    ...overrides,
  };
}
