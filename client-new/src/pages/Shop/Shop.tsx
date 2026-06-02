import { useEffect, useMemo, useState } from 'react';
import * as Icons from 'lucide-react';
import { ShoppingBag, BadgeCheck, Shield, Crown, RefreshCcw, Plus, Save, X, CircleOff, Coins as CoinsIcon, Pencil } from 'lucide-react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import {
  gamificationApi,
  type ShopItem,
  type ShopPurchase,
  type ShopShowcaseItem,
  type EquippedItem,
  type Achievement,
} from '../../api/gamification';
import { fetchCoinBalance } from '../../store/slices/coinsSlice';
import { t } from '../../i18n';
import styles from './Shop.module.css';

const categoryIcon: Record<string, React.ReactNode> = {
  status: <Shield size={16} />,
  badge: <BadgeCheck size={16} />,
  perk: <Crown size={16} />,
};

type FormState = {
  title: string;
  description: string;
  price: number;
  icon: string;
  category: 'status' | 'badge' | 'perk';
  rarity: 'common' | 'rare' | 'epic' | 'legendary';
  level_required: number;
  is_featured: boolean;
  image_url: string;
  stock: number | null;
  is_active: boolean;
};

const defaultForm: FormState = {
  title: '',
  description: '',
  price: 10,
  icon: 'BadgeCheck',
  category: 'status',
  rarity: 'common',
  level_required: 1,
  is_featured: false,
  image_url: '',
  stock: null,
  is_active: true,
};

function resolveIcon(name?: string | null) {
  if (!name) return <ShoppingBag size={26} />;
  const IconCmp = (Icons as Record<string, any>)[name];
  if (IconCmp) return <IconCmp size={26} />;
  return <ShoppingBag size={26} />;
}

export default function ShopPage() {
  const dispatch = useAppDispatch();
  const { user } = useAppSelector(s => s.auth);
  const { balance, loading: balanceLoading } = useAppSelector(s => s.coins);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [items, setItems] = useState<ShopItem[]>([]);
  const [showcase, setShowcase] = useState<ShopShowcaseItem[]>([]);
  const [purchases, setPurchases] = useState<ShopPurchase[]>([]);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [equipped, setEquipped] = useState<EquippedItem[]>([]);
  const [userLevel, setUserLevel] = useState(1);
  const [rarityFilter, setRarityFilter] = useState<'all' | 'common' | 'rare' | 'epic' | 'legendary'>('all');
  const [loading, setLoading] = useState(true);
  const [purchasesLoading, setPurchasesLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [buyingId, setBuyingId] = useState<string | null>(null);
  const [equippingId, setEquippingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(defaultForm);

  const isAdmin = user?.role === 'admin';

  const categoryLabel = useMemo<Record<string, string>>(() => ({
    status: lang.shop?.categoryStatus || 'Статус',
    badge: lang.shop?.categoryBadge || 'Бейдж',
    perk: lang.shop?.categoryPerk || 'Перк',
  }), [lang.shop]);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [itemsRes, showcaseRes, purchasesRes, achievementsRes, equippedRes, balanceRes] = await Promise.all([
        gamificationApi.getShopItems(),
        gamificationApi.getShopShowcase(),
        gamificationApi.getMyPurchases(),
        gamificationApi.getAchievements(),
        gamificationApi.getEquipped(),
        gamificationApi.getBalance(),
      ]);
      setItems(itemsRes.data);
      setShowcase(showcaseRes.data);
      setPurchases(purchasesRes.data);
      setAchievements(achievementsRes.data);
      setEquipped(equippedRes.data);
      setUserLevel(Math.max(1, Math.floor((balanceRes.data.total_earned || 0) / 100) + 1));
      dispatch(fetchCoinBalance());
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось загрузить магазин');
    } finally {
      setLoading(false);
    }
  };

  const loadPurchases = async () => {
    setPurchasesLoading(true);
    try {
      const [p, eq, ach] = await Promise.all([
        gamificationApi.getMyPurchases(),
        gamificationApi.getEquipped(),
        gamificationApi.getAchievements(),
      ]);
      setPurchases(p.data);
      setEquipped(eq.data);
      setAchievements(ach.data);
    } finally {
      setPurchasesLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetForm = () => {
    setForm(defaultForm);
    setEditingId(null);
  };

  const handleSave = async () => {
    if (!form.title.trim() || form.price <= 0) return;
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        await gamificationApi.updateShopItem(editingId, {
          title: form.title.trim(),
          description: form.description.trim() || null,
          price: form.price,
          icon: form.icon || null,
          category: form.category,
          rarity: form.rarity,
          level_required: form.level_required,
          is_featured: form.is_featured,
          image_url: form.image_url || null,
          stock: form.stock ?? null,
          is_active: form.is_active,
        });
        setSuccess('Товар обновлён');
      } else {
        await gamificationApi.createShopItem({
          title: form.title.trim(),
          description: form.description.trim() || undefined,
          price: form.price,
          icon: form.icon || undefined,
          category: form.category,
          rarity: form.rarity,
          level_required: form.level_required,
          is_featured: form.is_featured,
          image_url: form.image_url || undefined,
          stock: form.stock ?? undefined,
        });
        setSuccess('Товар создан');
      }
      await loadAll();
      resetForm();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Ошибка сохранения');
    } finally {
      setSaving(false);
      setTimeout(() => setSuccess(null), 2500);
    }
  };

  const handleEdit = (item: ShopItem) => {
    setEditingId(item.id);
    setForm({
      title: item.title,
      description: item.description || '',
      price: item.price,
      icon: item.icon || '',
      category: item.category as FormState['category'],
      rarity: item.rarity,
      level_required: item.level_required,
      is_featured: item.is_featured,
      image_url: item.image_url || '',
      stock: item.stock,
      is_active: item.is_active,
    });
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Удалить товар?')) return;
    setSaving(true);
    try {
      await gamificationApi.deleteShopItem(id);
      await loadAll();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось удалить товар');
    } finally {
      setSaving(false);
    }
  };

  const handleBuy = async (id: string) => {
    setBuyingId(id);
    setError(null);
    try {
      await gamificationApi.buyItem(id);
      await Promise.all([loadAll(), loadPurchases()]);
      setSuccess('Покупка успешна');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось купить');
    } finally {
      setBuyingId(null);
      setTimeout(() => setSuccess(null), 2500);
    }
  };

  const handleEquip = async (purchaseId: string) => {
    setEquippingId(purchaseId);
    try {
      await gamificationApi.equipPurchase(purchaseId);
      await loadPurchases();
      setSuccess('Предмет экипирован');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось экипировать предмет');
    } finally {
      setEquippingId(null);
      setTimeout(() => setSuccess(null), 2500);
    }
  };

  const filteredItems = useMemo(() => {
    const list = (showcase.length ? showcase : items).slice();
    if (rarityFilter !== 'all') {
      return list.filter((i: any) => i.rarity === rarityFilter).sort((a: any, b: any) => a.price - b.price);
    }
    return list.sort((a: any, b: any) => a.price - b.price);
  }, [showcase, items, rarityFilter]);

  return (
    <div className={styles.page}>
      <div className={styles.pageHead}>
        <div>
          <p className={styles.eyebrow}>{lang.shop?.title || 'Магазин Agile.Coins'}</p>
          <h1 className={styles.title}>{lang.shop?.subtitle || 'Получайте бейджи, статусы и перки'}</h1>
          <p className={styles.muted}>{lang.shop?.hint || 'Расходуйте Agile.Coins на награды. Админы могут управлять товарами.'}</p>
        </div>
        <div className={styles.balanceCard}>
          <div className={styles.balanceLabel}>{lang.shop?.balanceLabel || 'Баланс Agile.Coins'}</div>
          <div className={styles.balanceValue}>{balanceLoading ? '...' : balance ?? 0}</div>
          <div className={styles.balanceMeta}>{lang.shop?.balanceMeta || 'Зарабатывайте, выполняя задания и тесты.'}</div>
          <div className={styles.levelBadge}>Уровень: {userLevel}</div>
        </div>
      </div>

      {error && <div className={styles.alertError}>{error}</div>}
      {success && <div className={styles.alertSuccess}>{success}</div>}

      {isAdmin && (
        <div className={styles.adminPanel}>
          <div className={styles.panelHead}>
            <div className={styles.panelTitle}>{editingId ? 'Редактирование товара' : 'Новый товар'}</div>
            <div className={styles.panelActions}>
              {editingId && <button className="btn btn-ghost btn-sm" onClick={resetForm}><X size={14} /> Сброс</button>}
              <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
                {editingId ? <><Save size={14} /> Сохранить</> : <><Plus size={14} /> Добавить</>}
              </button>
            </div>
          </div>
          <div className={styles.formGrid}>
            <label className={styles.formField}>
              <span>Название</span>
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} maxLength={255} />
            </label>
            <label className={styles.formField}>
              <span>Описание</span>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={2} />
            </label>
            <label className={styles.formField}>
              <span>Цена</span>
              <input type="number" min={1} value={form.price} onChange={e => setForm({ ...form, price: Number(e.target.value) })} />
            </label>
            <label className={styles.formField}>
              <span>Icon (lucide)</span>
              <input value={form.icon} onChange={e => setForm({ ...form, icon: e.target.value })} placeholder="BadgeCheck" />
            </label>
            <label className={styles.formField}>
              <span>Категория</span>
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value as FormState['category'] })}>
                <option value="status">{categoryLabel.status}</option>
                <option value="badge">{categoryLabel.badge}</option>
                <option value="perk">{categoryLabel.perk}</option>
              </select>
            </label>
            <label className={styles.formField}>
              <span>Редкость</span>
              <select value={form.rarity} onChange={e => setForm({ ...form, rarity: e.target.value as FormState['rarity'] })}>
                <option value="common">common</option>
                <option value="rare">rare</option>
                <option value="epic">epic</option>
                <option value="legendary">legendary</option>
              </select>
            </label>
            <label className={styles.formField}>
              <span>Минимальный уровень</span>
              <input type="number" min={1} max={100} value={form.level_required} onChange={e => setForm({ ...form, level_required: Number(e.target.value) || 1 })} />
            </label>
            <label className={styles.formField}>
              <span>Image URL</span>
              <input value={form.image_url} onChange={e => setForm({ ...form, image_url: e.target.value })} />
            </label>
            <label className={styles.formField}>
              <span>Stock (пусто = бесконечно)</span>
              <input type="number" min={0} value={form.stock ?? ''} onChange={e => setForm({ ...form, stock: e.target.value === '' ? null : Number(e.target.value) })} />
            </label>
            <label className={styles.checkboxField}>
              <input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} />
              <span>Активен</span>
            </label>
            <label className={styles.checkboxField}>
              <input type="checkbox" checked={form.is_featured} onChange={e => setForm({ ...form, is_featured: e.target.checked })} />
              <span>Витринный товар</span>
            </label>
          </div>
        </div>
      )}

      <div className={styles.sectionHeader}>
        <h2>{lang.shop?.itemsTitle || 'Товары'}</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div className={styles.rarityFilters}>
            {(['all', 'common', 'rare', 'epic', 'legendary'] as const).map((r) => (
              <button
                key={r}
                className={`btn btn-ghost btn-sm ${rarityFilter === r ? styles.rarityActive : ''}`}
                onClick={() => setRarityFilter(r)}
              >
                {r === 'all' ? 'Все' : r}
              </button>
            ))}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={loadAll}>
            <RefreshCcw size={14} /> Обновить
          </button>
        </div>
      </div>

      {loading ? (
        <div className={styles.empty}>{lang.common?.loading || 'Загрузка...'}</div>
      ) : filteredItems.length === 0 ? (
        <div className={styles.empty}>{lang.common?.noData || 'Пусто'}</div>
      ) : (
        <div className={styles.grid}>
          {filteredItems.map(item => {
            const ownedCount = (item as any).owned_count || 0;
            const isLocked = !!(item as any).is_locked;
            const outOfStock = item.stock !== null && item.stock <= 0;
            const inactive = !item.is_active;
            return (
              <div key={item.id} className={`${styles.card} ${inactive ? styles.cardMuted : ''}`} data-category={item.category}>
                <div className={styles.cardTop}>
                  <div className={styles.cardIcon}>{resolveIcon(item.icon)}</div>
                  <div className={styles.cardMeta}>
                    <div className={styles.cardTitle}>{item.title}</div>
                    <div className={styles.cardCategory}>
                      {categoryIcon[item.category] || <ShoppingBag size={14} />} {categoryLabel[item.category] || item.category}
                    </div>
                    <div className={`${styles.rarityTag} ${styles[`rarity_${item.rarity}`]}`}>{item.rarity}</div>
                  </div>
                  {isAdmin && (
                    <button className="btn btn-ghost btn-sm" onClick={() => handleEdit(item)} title="Редактировать"><Pencil size={14} /></button>
                  )}
                </div>
                {item.image_url && <img src={item.image_url} alt="" className={styles.cardImage} />}
                {item.description && <p className={styles.cardDesc}>{item.description}</p>}

                <div className={styles.cardFooter}>
                  <div className={styles.price}><CoinsIcon size={14} /> {item.price}</div>
                  {item.stock !== null && <span className={styles.stock}>{lang.shop?.stock || 'Остаток'}: {item.stock}</span>}
                  <span className={styles.stock}>Мин. уровень: {item.level_required}</span>
                  {ownedCount > 0 && <span className={styles.stock}>Куплено: {ownedCount}</span>}
                  {!item.is_active && <span className={styles.inactive}><CircleOff size={14} /> {lang.shop?.inactive || 'Скрыт'}</span>}
                  {isLocked && <span className={styles.inactive}><CircleOff size={14} /> Недоступно по уровню</span>}
                </div>

                <div className={styles.actions}>
                  {isAdmin ? (
                    <>
                      <button className="btn btn-ghost btn-sm" onClick={() => handleEdit(item)}>{lang.common?.edit || 'Изменить'}</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(item.id)} disabled={saving}>{lang.common?.delete || 'Удалить'}</button>
                    </>
                  ) : (
                    <>
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={inactive || outOfStock || isLocked || buyingId === item.id || !(item as any).can_buy}
                        onClick={() => handleBuy(item.id)}
                      >
                        {buyingId === item.id ? (lang.common?.loading || '...') : (lang.shop?.buy || 'Купить')}
                      </button>
                      {purchases.filter(p => p.item_id === item.id).map((p) => {
                        const isEquipped = equipped.some(e => e.purchase_id === p.id);
                        return (
                          <button
                            key={p.id}
                            className="btn btn-ghost btn-sm"
                            disabled={equippingId === p.id || isEquipped}
                            onClick={() => handleEquip(p.id)}
                          >
                            {isEquipped ? 'Экипировано' : (equippingId === p.id ? '...' : 'Экипировать')}
                          </button>
                        );
                      })}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className={styles.sectionHeader} style={{ marginTop: 28 }}>
        <h2>{lang.shop?.purchasesTitle || 'Мои покупки'}</h2>
        <button className="btn btn-ghost btn-sm" onClick={loadPurchases} disabled={purchasesLoading}>
          <RefreshCcw size={14} /> Обновить
        </button>
      </div>
      {purchasesLoading ? (
        <div className={styles.empty}>{lang.common?.loading || 'Загрузка...'}</div>
      ) : purchases.length === 0 ? (
        <div className={styles.empty}>{lang.shop?.noPurchases || 'Вы ещё ничего не покупали.'}</div>
      ) : (
        <div className={styles.list}>
          {purchases.map(p => (
            <div key={p.id} className={styles.purchaseRow}>
              <div>
                <div className={styles.purchaseTitle}>{p.item_title}</div>
                <div className={styles.purchaseDate}>{new Date(p.created_at).toLocaleString()}</div>
              </div>
              <div className={styles.purchasePrice}><CoinsIcon size={14} /> {p.price_paid}</div>
            </div>
          ))}
        </div>
      )}

      <div className={styles.sectionHeader} style={{ marginTop: 22 }}>
        <h2>Достижения</h2>
      </div>
      {achievements.length === 0 ? (
        <div className={styles.empty}>Купите товары, чтобы открыть достижения.</div>
      ) : (
        <div className={styles.achievementsGrid}>
          {achievements.map((a) => (
            <div key={a.id} className={`${styles.achievementCard} ${a.unlocked ? styles.achievementUnlocked : ''}`}>
              <div className={styles.achievementHead}>
                <span className={`${styles.rarityTag} ${styles[`rarity_${a.rarity}`]}`}>{a.rarity}</span>
                <strong>Lv.{a.level}</strong>
              </div>
              <div className={styles.achievementTitle}>{a.title}</div>
              <div className={styles.achievementProgress}>{a.progress} / {a.target}</div>
              <div className={styles.progressBar}><span style={{ width: `${Math.min(100, (a.progress / Math.max(1, a.target)) * 100)}%` }} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
