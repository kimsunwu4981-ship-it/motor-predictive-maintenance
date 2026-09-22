import type { ModeData } from "../data";
import type { ModeContent } from "../content/types";

export function Glossary({ data, content }: { data: ModeData; content: ModeContent }) {
  return (
    <dl className="gloss">
      {content.glossary(data).map((g) => (
        <div key={g.term}><dt>{g.term}</dt><dd>{g.body}</dd></div>
      ))}
    </dl>
  );
}
