import type { Mode } from "../data";
import type { ModeContent } from "./types";
import { mechanical } from "./mechanical";
import { electrical } from "./electrical";

export const CONTENT: Record<Mode, ModeContent> = { mechanical, electrical };
