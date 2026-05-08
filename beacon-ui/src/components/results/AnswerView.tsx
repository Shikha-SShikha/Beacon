import type { AskResponse } from "../../types";

interface Props {
  response: AskResponse;
  onCitationClick: (citationId: number) => void;
}

export default function AnswerView({ response, onCitationClick }: Props) {
  const parts = response.answer.split(/(\[\d+\])/g);

  return (
    <div className="max-w-none">
      <div className="text-[15px] text-slate-700 leading-[1.75] whitespace-pre-line">
        {parts.map((part, i) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (match) {
            const cid = parseInt(match[1], 10);
            return (
              <button
                key={i}
                onClick={() => onCitationClick(cid)}
                className="inline-flex items-center justify-center min-w-[1.35rem] h-[1.35rem] px-1 mx-0.5 rounded-md text-[11px] font-bold bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors cursor-pointer align-super leading-none"
                title={`View source ${cid}`}
              >
                {cid}
              </button>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </div>
    </div>
  );
}
