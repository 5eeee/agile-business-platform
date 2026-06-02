import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface MusicTrack {
  id: string;
  title: string;
  artist?: string;
  file_url: string;
  duration?: number;
  order: number;
}

interface MusicState {
  tracks: MusicTrack[];
  currentIndex: number;
  isPlaying: boolean;
  volume: number;
  playlistId: string | null;
  playlistName: string | null;
}

const initialState: MusicState = {
  tracks: [],
  currentIndex: -1,
  isPlaying: false,
  volume: 0.7,
  playlistId: null,
  playlistName: null,
};

const musicSlice = createSlice({
  name: 'music',
  initialState,
  reducers: {
    setPlaylist(state, action: PayloadAction<{ id: string; name: string; tracks: MusicTrack[] }>) {
      state.playlistId = action.payload.id;
      state.playlistName = action.payload.name;
      state.tracks = action.payload.tracks;
    },
    playTrack(state, action: PayloadAction<number>) {
      state.currentIndex = action.payload;
      state.isPlaying = true;
    },
    togglePlay(state) {
      state.isPlaying = !state.isPlaying;
    },
    pause(state) {
      state.isPlaying = false;
    },
    resume(state) {
      if (state.currentIndex >= 0) state.isPlaying = true;
    },
    nextTrack(state) {
      if (state.currentIndex < state.tracks.length - 1) {
        state.currentIndex += 1;
        state.isPlaying = true;
      }
    },
    prevTrack(state) {
      if (state.currentIndex > 0) {
        state.currentIndex -= 1;
        state.isPlaying = true;
      }
    },
    setVolume(state, action: PayloadAction<number>) {
      state.volume = action.payload;
    },
  },
});

export const { setPlaylist, playTrack, togglePlay, pause, resume, nextTrack, prevTrack, setVolume } = musicSlice.actions;
export default musicSlice.reducer;
