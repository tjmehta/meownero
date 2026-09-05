import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: "https://meownero.com",
      lastModified: new Date("2026-09-05"),
      changeFrequency: "monthly",
      priority: 1,
    },
  ];
}
