import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Overview } from "./pages/Overview";
import { AccountDetail } from "./pages/AccountDetail";
import { Compare } from "./pages/Compare";
import { ContentLibrary } from "./pages/ContentLibrary";
import { Flow } from "./pages/Flow";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/content" element={<ContentLibrary />} />
        <Route path="/flow" element={<Flow />} />
        <Route path="/accounts/:id" element={<AccountDetail />} />
      </Routes>
    </Layout>
  );
}
