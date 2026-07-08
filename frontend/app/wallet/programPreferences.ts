import { Program } from "../../lib/walletApi";

export const FAVORITE_PROGRAM_PREF_KEY = "phistyle.wallet.favoritePrograms";

export const DEFAULT_FAVORITE_PROGRAMS: Array<{ label: string; aliases: string[] }> = [
  { label: "Hilton", aliases: ["hilton", "希爾頓"] },
  { label: "IHG", aliases: ["ihg", "洲際"] },
  { label: "萬豪", aliases: ["marriott", "萬豪", "bonvoy"] },
  { label: "Choice", aliases: ["choice"] },
  { label: "Hyatt", aliases: ["hyatt", "凱悅"] },
  { label: "Alaska", aliases: ["alaska", "mileage plan"] },
  { label: "Aeroplan", aliases: ["aeroplan", "air canada", "加拿大"] },
  { label: "長榮", aliases: ["eva", "長榮"] },
  { label: "亞萬", aliases: ["cathay", "asia miles", "asiamiles", "亞洲萬里通", "亞萬"] },
  { label: "ANA", aliases: ["ana", "全日空"] },
  { label: "JAL", aliases: ["jal", "日航"] },
  { label: "Qatar", aliases: ["qatar", "qr", "卡達"] },
];

const FAVORITE_BASE_RANK = 1000;
const NON_FAVORITE_BASE_RANK = 10000;

export function defaultFavoriteProgramIds(programs: Program[]): number[] {
  const ids: number[] = [];
  for (const group of DEFAULT_FAVORITE_PROGRAMS) {
    const program = findProgramByAliases(programs, group.aliases);
    if (program && !ids.includes(program.id)) ids.push(program.id);
  }
  return ids;
}

export function sortPrograms(programs: Program[], favoriteProgramIds: number[]): Program[] {
  return [...programs].sort((left, right) => {
    const leftRank = programRank(left, favoriteProgramIds);
    const rightRank = programRank(right, favoriteProgramIds);
    if (leftRank !== rightRank) return leftRank - rightRank;
    return compareProgramName(left.name, right.name);
  });
}

export function programDisplayName(program: Program, favoriteProgramIds: number[]): string {
  return `${favoriteProgramIds.includes(program.id) ? "⭐ " : ""}${program.name}`;
}

export function findProgramByAliases(programs: Program[], aliases: string[]): Program | null {
  return programs.find((program) => matchesAliases(program.name, aliases)) || null;
}

function programRank(program: Program, favoriteProgramIds: number[]): number {
  const defaultRank = DEFAULT_FAVORITE_PROGRAMS.findIndex((group) => matchesAliases(program.name, group.aliases));
  if (favoriteProgramIds.includes(program.id)) {
    return defaultRank >= 0 ? defaultRank : FAVORITE_BASE_RANK;
  }
  return NON_FAVORITE_BASE_RANK;
}

function matchesAliases(name: string, aliases: string[]): boolean {
  const normalizedName = normalizeName(name);
  return aliases.some((alias) => normalizedName.includes(normalizeName(alias)));
}

function compareProgramName(left: string, right: string): number {
  return left.localeCompare(right, ["zh-Hant", "en"], { sensitivity: "base" });
}

function normalizeName(value: string): string {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}
