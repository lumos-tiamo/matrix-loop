import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Overview } from "./pages/Overview";
import { AccountDetail } from "./pages/AccountDetail";
import { Compare } from "./pages/Compare";
import { ContentLibrary } from "./pages/ContentLibrary";
import { Flow } from "./pages/Flow";
import { Video } from "./pages/Video";
import { Schedule } from "./pages/Schedule";
import { Carousels } from "./pages/Carousels";
import { Flywheel } from "./pages/Flywheel";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Flywheel />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/content" element={<ContentLibrary />} />
        <Route path="/flow" element={<Flow />} />
        <Route path="/video" element={<Video />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/carousels" element={<Carousels />} />
        <Route path="/accounts/:id" element={<AccountDetail />} />
      </Routes>
    </Layout>
  );
}
