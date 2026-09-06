import { markdownBlocks } from "../lib/artifactReader";

export default function ArtifactMarkdown({ markdown, headingLevel = 3 }: { markdown: string; headingLevel?: 3 | 4 }) {
  const Heading = headingLevel === 4 ? "h4" : "h3";
  return <>{markdownBlocks(markdown).map((block, index) => block.kind === "table"
    ? <div className="table-wrap" tabIndex={0} role="region" aria-label={`Analysis table ${index + 1}`} key={index}><table><thead><tr>{block.headers.map((cell, column) => <th scope="col" key={column}>{cell}</th>)}</tr></thead><tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, column) => <td key={column}>{cell}</td>)}</tr>)}</tbody></table></div>
    : block.kind === "heading" ? <Heading key={index}>{block.text}</Heading> : <p key={index}>{block.text}</p>)}</>;
}
