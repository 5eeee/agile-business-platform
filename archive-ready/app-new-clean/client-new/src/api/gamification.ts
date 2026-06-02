import api from './client';

/* ============ Types ============ */

export interface CoinBalance {
  balance: number;
  total_earned: number;
  total_spent: number;
}

export interface CoinTransaction {
  id: string;
  amount: number;
  tx_type: string;
  reason: string | null;
  granted_by_name: string | null;
  created_at: string;
}

export interface ShopItem {
  id: string;
  title: string;
  description: string | null;
  price: number;
  icon: string | null;
  category: string;
  image_url: string | null;
  is_active: boolean;
  stock: number | null;
  rarity: 'common' | 'rare' | 'epic' | 'legendary';
  level_required: number;
  is_featured: boolean;
  created_at: string;
}

export interface ShopShowcaseItem extends ShopItem {
  owned_count: number;
  can_buy: boolean;
  is_locked: boolean;
  next_tier_required: number;
}

export interface ShopPurchase {
  id: string;
  item_id: string;
  item_title: string;
  price_paid: number;
  rarity: 'common' | 'rare' | 'epic' | 'legendary';
  category: 'status' | 'badge' | 'perk';
  created_at: string;
}

export interface EquippedItem {
  category: string;
  purchase_id: string;
  item_id: string;
  item_title: string;
  rarity: 'common' | 'rare' | 'epic' | 'legendary';
  equipped_at: string;
}

export interface Achievement {
  id: string;
  title: string;
  category: string;
  rarity: 'common' | 'rare' | 'epic' | 'legendary';
  level: number;
  progress: number;
  target: number;
  unlocked: boolean;
  icon: string | null;
}

export interface TestResult {
  id: string;
  topic_id: string;
  score: number;
  total: number;
  passed: boolean;
  attempt: number;
  created_at: string;
}

export interface UserKPI {
  user_id: string;
  user_name: string;
  avatar_url: string | null;
  total_time_minutes: number;
  topics_completed: number;
  topics_total: number;
  tests_passed: number;
  tests_total: number;
  avg_test_score: number;
  coins_balance: number;
  completion_pct: number;
  speed_topics_per_day: number;
  retention_pct: number;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: string;
  user_name: string;
  avatar_url: string | null;
  coins_balance: number;
  topics_completed: number;
  avg_test_score: number;
  total_time_hours: number;
  tasks_assigned: number;
  tasks_completed_week: number;
  tasks_completed_day: number;
  tasks_completed_month: number;
  tasks_completed_year: number;
  tasks_overdue: number;
  training_progress_pct: number;
  coins_earned_tasks: number;
  anti_cheat_score: number;
  anti_cheat_flags: string[];
}

export interface SectionAccess {
  user_id: string;
  section_keys: string[];
}

/* ============ API ============ */

export const gamificationApi = {
  // Coins
  getBalance: () =>
    api.get<CoinBalance>('/gamification/coins/balance'),
  getCoinHistory: () =>
    api.get<CoinTransaction[]>('/gamification/coins/history'),
  grantCoins: (data: { user_id: string; amount: number; reason: string }) =>
    api.post<CoinTransaction>('/gamification/coins/grant', data),

  // Shop
  getShopItems: () =>
    api.get<ShopItem[]>('/gamification/shop/items'),
  getShopShowcase: () =>
    api.get<ShopShowcaseItem[]>('/gamification/shop/showcase'),
  createShopItem: (data: { title: string; description?: string; price: number; icon?: string; category?: string; image_url?: string; stock?: number; rarity?: string; level_required?: number; is_featured?: boolean }) =>
    api.post<ShopItem>('/gamification/shop/items', data),
  updateShopItem: (id: string, data: Partial<ShopItem>) =>
    api.put<ShopItem>(`/gamification/shop/items/${encodeURIComponent(id)}`, data),
  deleteShopItem: (id: string) =>
    api.delete(`/gamification/shop/items/${encodeURIComponent(id)}`),
  buyItem: (id: string) =>
    api.post<ShopPurchase>(`/gamification/shop/buy/${encodeURIComponent(id)}`),
  getMyPurchases: () =>
    api.get<ShopPurchase[]>('/gamification/shop/my-purchases'),
  getAchievements: () =>
    api.get<Achievement[]>('/gamification/shop/achievements'),
  getEquipped: () =>
    api.get<EquippedItem[]>('/gamification/shop/equipped'),
  equipPurchase: (purchaseId: string) =>
    api.post<EquippedItem>(`/gamification/shop/equip/${encodeURIComponent(purchaseId)}`),

  // Tests
  submitTest: (data: { topic_id: string; score: number; total: number }) =>
    api.post<TestResult>('/gamification/test/submit', data),
  getTestResults: () =>
    api.get<TestResult[]>('/gamification/test/results'),
  getTopicTestResult: (topicId: string) =>
    api.get<TestResult>(`/gamification/test/topic/${encodeURIComponent(topicId)}`),

  // KPI
  getMyKPI: () =>
    api.get<UserKPI>('/gamification/kpi/me'),
  getUserKPI: (userId: string) =>
    api.get<UserKPI>(`/gamification/kpi/user/${encodeURIComponent(userId)}`),

  // Leaderboard
  getLeaderboard: () =>
    api.get<LeaderboardEntry[]>('/gamification/leaderboard'),

  // Session tracking
  sessionPing: () =>
    api.post('/gamification/session/ping'),
  sessionEnd: () =>
    api.post('/gamification/session/end'),

  // Section access
  grantAccess: (data: { user_id: string; section_keys: string[] }) =>
    api.post('/gamification/access/grant', data),
  setAccess: (userId: string, sectionKeys: string[]) =>
    api.put(`/gamification/access/${encodeURIComponent(userId)}`, { section_keys: sectionKeys }),
  getAccess: (userId: string) =>
    api.get<SectionAccess>(`/gamification/access/${encodeURIComponent(userId)}`),
};
