import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "League", end: true },
  { to: "/cumulative", label: "Cumulative 2026", end: false },
  { to: "/all-time", label: "All-Time", end: false },
  { to: "/head-to-head", label: "Head-to-Head", end: false },
];

export default function Nav() {
  return (
    <nav className="flex justify-center mt-4 mb-6">
      <div className="inline-flex gap-1 bg-[#0f3460] p-1 rounded-md">
        {links.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              [
                "px-[18px] py-[7px] rounded-[7px] text-[0.82em] font-medium transition-all duration-200 tracking-[0.3px] no-underline",
                isActive
                  ? "bg-[#e94560] text-white font-semibold"
                  : "text-[#888] hover:text-[#e0e0e0] hover:bg-white/[0.06]",
              ].join(" ")
            }
          >
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
