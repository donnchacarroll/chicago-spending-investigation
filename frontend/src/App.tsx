import { BrowserRouter, Routes, Route } from "react-router-dom";
import { DateFilterProvider } from "./lib/DateFilterContext";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Payments from "./pages/Payments";
import Vendors from "./pages/Vendors";
import Departments from "./pages/Departments";
import Alerts from "./pages/Alerts";
import Trends from "./pages/Trends";
import Categories from "./pages/Categories";
import Contracts from "./pages/Contracts";
import Network from "./pages/Network";
import Donations from "./pages/Donations";
import Methodology from "./pages/Methodology";

export default function App() {
  return (
    <DateFilterProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/trends" element={<Trends />} />
            <Route path="/payments" element={<Payments />} />
            <Route path="/vendors" element={<Vendors />} />
            <Route path="/network" element={<Network />} />
            <Route path="/departments" element={<Departments />} />
            <Route path="/categories" element={<Categories />} />
            <Route path="/contracts" element={<Contracts />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/donations" element={<Donations />} />
            <Route path="/methodology" element={<Methodology />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DateFilterProvider>
  );
}
