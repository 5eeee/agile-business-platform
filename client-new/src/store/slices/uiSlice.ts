import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { RTL_LANGUAGES } from '../../i18n';

export type Language = 'ru' | 'ka' | 'en' | 'ar';

interface UIState {
  theme: 'light' | 'dark';
  language: Language;
  sidebarOpen: boolean;
  /** Узкий режим (только иконки), как в YouGile */
  sidebarNarrow: boolean;
  mobileMenuOpen: boolean;
}

const savedLang = (localStorage.getItem('language') as Language) || 'ru';

const initialState: UIState = {
  theme: (localStorage.getItem('theme') as 'light' | 'dark') || 'light',
  language: savedLang,
  sidebarOpen: true,
  sidebarNarrow: localStorage.getItem('sidebarNarrow') === '1',
  mobileMenuOpen: false,
};

// Инициализация темы и направления при загрузке
document.documentElement.setAttribute('data-theme', initialState.theme);
document.documentElement.dir = RTL_LANGUAGES.includes(savedLang) ? 'rtl' : 'ltr';

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleTheme(state) {
      state.theme = state.theme === 'light' ? 'dark' : 'light';
      localStorage.setItem('theme', state.theme);
      document.documentElement.setAttribute('data-theme', state.theme);
    },
    setLanguage(state, action: PayloadAction<Language>) {
      state.language = action.payload;
      localStorage.setItem('language', action.payload);
      document.documentElement.dir = RTL_LANGUAGES.includes(action.payload) ? 'rtl' : 'ltr';
    },
    toggleSidebar(state) {
      state.sidebarOpen = !state.sidebarOpen;
    },
    toggleSidebarNarrow(state) {
      state.sidebarNarrow = !state.sidebarNarrow;
      localStorage.setItem('sidebarNarrow', state.sidebarNarrow ? '1' : '0');
    },
    setSidebarNarrow(state, action: PayloadAction<boolean>) {
      state.sidebarNarrow = action.payload;
      localStorage.setItem('sidebarNarrow', action.payload ? '1' : '0');
    },
    toggleMobileMenu(state) {
      state.mobileMenuOpen = !state.mobileMenuOpen;
    },
  },
});

export const { toggleTheme, setLanguage, toggleSidebar, toggleSidebarNarrow, setSidebarNarrow, toggleMobileMenu } =
  uiSlice.actions;
export default uiSlice.reducer;
