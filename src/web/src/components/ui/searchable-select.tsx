import * as React from "react";
import { ChevronDownIcon, MagnifyingGlassIcon, XMarkIcon } from "@heroicons/react/24/outline";

export interface SearchableOption {
	value: string | number;
	label: string;
	description?: string;
}

interface SearchableSelectProps {
	id?: string;
	label?: string;
	options: SearchableOption[];
	value: string | number | "";
	onChange: (value: any) => void;
	placeholder?: string;
	required?: boolean;
	disabled?: boolean;
	className?: string;
}

export function SearchableSelect({
	id,
	label,
	options,
	value,
	onChange,
	placeholder = "Select or search...",
	required = false,
	disabled = false,
	className = "",
}: SearchableSelectProps) {
	const [isOpen, setIsOpen] = React.useState(false);
	const [searchQuery, setSearchQuery] = React.useState("");
	const containerRef = React.useRef<HTMLDivElement>(null);

	const selectedOption = options.find((opt) => String(opt.value) === String(value));

	const filteredOptions = React.useMemo(() => {
		if (!searchQuery.trim()) return options;
		const q = searchQuery.toLowerCase();
		return options.filter(
			(opt) =>
				opt.label.toLowerCase().includes(q) ||
				(opt.description && opt.description.toLowerCase().includes(q))
		);
	}, [options, searchQuery]);

	React.useEffect(() => {
		function handleClickOutside(event: MouseEvent) {
			if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
				setIsOpen(false);
			}
		}
		document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, []);

	return (
		<div className={`relative space-y-1 ${className}`} ref={containerRef}>
			{label && (
				<label htmlFor={id} className="text-xs font-medium text-slate-700 block">
					{label} {required && <span className="text-red-500">*</span>}
				</label>
			)}

			<button
				id={id}
				type="button"
				disabled={disabled}
				onClick={() => setIsOpen((prev) => !prev)}
				className={`w-full flex items-center justify-between px-3 py-2 text-xs rounded-md border bg-white transition cursor-pointer text-left ${
					isOpen ? "border-slate-900 ring-1 ring-slate-900" : "border-slate-200 hover:border-slate-300"
				} ${disabled ? "opacity-50 cursor-not-allowed bg-slate-50" : ""}`}
			>
				<span className={selectedOption ? "text-slate-900 font-medium" : "text-slate-400"}>
					{selectedOption ? selectedOption.label : placeholder}
				</span>
				<ChevronDownIcon className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-2" />
			</button>

			{isOpen && (
				<div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-xl overflow-hidden animate-in fade-in-0 zoom-in-95 duration-100">
					<div className="p-2 border-b border-slate-100 bg-slate-50/50 flex items-center gap-2">
						<MagnifyingGlassIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
						<input
							type="text"
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							placeholder="Type to search..."
							autoFocus
							className="w-full text-xs bg-transparent focus:outline-hidden text-slate-900 placeholder:text-slate-400"
						/>
						{searchQuery && (
							<button
								type="button"
								onClick={() => setSearchQuery("")}
								className="text-slate-400 hover:text-slate-600 p-0.5"
							>
								<XMarkIcon className="w-3 h-3" />
							</button>
						)}
					</div>

					<div className="max-h-56 overflow-y-auto divide-y divide-slate-50 p-1">
						{filteredOptions.length === 0 ? (
							<div className="p-3 text-center text-xs text-slate-400">
								No matching results found
							</div>
						) : (
							filteredOptions.map((opt) => {
								const isSelected = String(opt.value) === String(value);
								return (
									<button
										key={opt.value}
										type="button"
										onClick={() => {
											onChange(opt.value);
											setIsOpen(false);
											setSearchQuery("");
										}}
										className={`w-full text-left px-2.5 py-2 rounded-md text-xs transition cursor-pointer flex flex-col gap-0.5 ${
											isSelected
												? "bg-slate-900 text-white font-medium"
												: "hover:bg-slate-100 text-slate-800"
										}`}
									>
										<span>{opt.label}</span>
										{opt.description && (
											<span
												className={`text-[10px] ${
													isSelected ? "text-slate-300" : "text-slate-400"
												}`}
											>
												{opt.description}
											</span>
										)}
									</button>
								);
							})
						)}
					</div>
				</div>
			)}
		</div>
	);
}
