import type { Metadata } from "next";
import { notFound } from "next/navigation";
import RouteForwarder from "../../src/components/RouteForwarder";
import { destinationFromSlug, forwardedSlug, routeSlugs } from "../../src/lib/workbench";

// The static route set is exactly the destination table plus its forwarders
// (lib/workbench#routeSlugs); nothing here adds or omits a route.
export function generateStaticParams() {
  return routeSlugs.map((destination) => ({ destination }));
}

export async function generateMetadata({ params }: { params: Promise<{ destination: string }> }): Promise<Metadata> {
  const { destination } = await params;
  const known = destinationFromSlug(destination) !== null;
  // A forwarded slug carries its destination's tab title from the first paint.
  return { title: known ? `CAOS — ${destinationFromSlug(destination)}` : "CAOS — Not found" };
}

export default async function DestinationPage({ params }: { params: Promise<{ destination: string }> }) {
  const { destination } = await params;
  if (destinationFromSlug(destination) === null) notFound();
  const forward = forwardedSlug(destination);
  // A forwarded slug renders the forwarder and nothing else; a destination renders
  // nothing here because the Workspace in the root layout renders every surface
  // from the pathname.
  if (forward) return <RouteForwarder to={`/${forward}/`} />;
  return null;
}
