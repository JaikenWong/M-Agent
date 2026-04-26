import { create } from "zustand";
import type { Task } from "@/types";
import { api } from "@/api/endpoints";

interface TaskState {
  tasks: Task[];
  loading: boolean;
  fetchTasks: () => Promise<void>;
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  loading: false,

  fetchTasks: async () => {
    set({ loading: true });
    try {
      const tasks = await api.listTasks();
      set({ tasks });
    } finally {
      set({ loading: false });
    }
  },
}));
