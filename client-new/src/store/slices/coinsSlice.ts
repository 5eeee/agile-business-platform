import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { gamificationApi, type CoinBalance, type CoinTransaction } from '../../api/gamification';

interface CoinsState {
  balance: number | null;
  totalEarned: number;
  totalSpent: number;
  history: CoinTransaction[];
  loading: boolean;
  historyLoading: boolean;
  error: string | null;
}

const initialState: CoinsState = {
  balance: null,
  totalEarned: 0,
  totalSpent: 0,
  history: [],
  loading: false,
  historyLoading: false,
  error: null,
};

export const fetchCoinBalance = createAsyncThunk('coins/fetchBalance', async () => {
  const { data } = await gamificationApi.getBalance();
  return data;
});

export const fetchCoinHistory = createAsyncThunk('coins/fetchHistory', async () => {
  const { data } = await gamificationApi.getCoinHistory();
  return data;
});

const coinsSlice = createSlice({
  name: 'coins',
  initialState,
  reducers: {
    setBalance(state, action: PayloadAction<CoinBalance>) {
      state.balance = action.payload.balance;
      state.totalEarned = action.payload.total_earned;
      state.totalSpent = action.payload.total_spent;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCoinBalance.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchCoinBalance.fulfilled, (state, action) => {
        state.loading = false;
        state.balance = action.payload.balance;
        state.totalEarned = action.payload.total_earned;
        state.totalSpent = action.payload.total_spent;
      })
      .addCase(fetchCoinBalance.rejected, (state, action) => {
        state.loading = false;
        state.error = typeof action.error.message === 'string' ? action.error.message : 'Failed to load balance';
      })
      .addCase(fetchCoinHistory.pending, (state) => {
        state.historyLoading = true;
        state.error = null;
      })
      .addCase(fetchCoinHistory.fulfilled, (state, action) => {
        state.historyLoading = false;
        state.history = action.payload;
      })
      .addCase(fetchCoinHistory.rejected, (state, action) => {
        state.historyLoading = false;
        state.error = typeof action.error.message === 'string' ? action.error.message : 'Failed to load history';
      });
  },
});

export const { setBalance } = coinsSlice.actions;
export default coinsSlice.reducer;
