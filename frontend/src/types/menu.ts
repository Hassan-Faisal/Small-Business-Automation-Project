export type MealType = "breakfast" | "lunch" | "dinner";

export type DayOfWeek =
  | "Monday"
  | "Tuesday"
  | "Wednesday"
  | "Thursday"
  | "Friday"
  | "Saturday"
  | "Sunday";

export interface MenuItem {
  id: number;
  name: string;
  description: string | null;
  price: string | number;
  meal_type: MealType;
  day_of_week: DayOfWeek;
  availability: boolean;
  is_active: boolean;
}

export interface MenuItemListResponse {
  items: MenuItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateMenuItemPayload {
  name: string;
  description: string | null;
  price: string;
  meal_type: MealType;
  day_of_week: DayOfWeek;
  availability: boolean;
  is_active: boolean;
}

export interface UpdateMenuItemPayload {
  description: string | null;
  price: string;
  availability: boolean;
}
