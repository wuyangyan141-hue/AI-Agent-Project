import { useMemo, useRef, useState } from 'react';
import { DogAvatar } from './DogAvatar';
import type { KnowledgeDocument } from './knowledge';
import type { LearningProject } from './knowledge';
import type { PanelTab } from './desktop';
import type { PetState } from './protocol';

type Props = {
  petName: string;
  petState: PetState;
  tab: PanelTab;
  documents: KnowledgeDocument[];
  projects: LearningProject[];
  activeProjectId: string | null;
  libraryCount: number;
  busy?: boolean;
  onShowPet: () => void;
  onSelectTab: (tab: PanelTab) => void;
  onSelectProject: (project: LearningProject) => void;
  onCreateProject: () => void;
  onRenameProject: (project: LearningProject) => void;
  onDeleteProject: (project: LearningProject) => void;
  onAttachFile: (projectId: string, documentId: string) => void;
  onDetachFile: (projectId: string, documentId: string) => void;
  onUploadToProject: (projectId: string, files: FileList | File[]) => void;
};

const toolNav: { key: PanelTab; label: string }[] = [
  { key: 'library', label: '资料库' },
  { key: 'tasks', label: '任务' },
  { key: 'memory', label: '偏好' },
  { key: 'history', label: '历史' },
  { key: 'settings', label: '设置' },
];

export function ProjectSidebar({
  petName,
  petState,
  tab,
  documents,
  projects,
  activeProjectId,
  libraryCount,
  busy,
  onShowPet,
  onSelectTab,
  onSelectProject,
  onCreateProject,
  onRenameProject,
  onDeleteProject,
  onAttachFile,
  onDetachFile,
  onUploadToProject,
}: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [pickerFor, setPickerFor] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const uploadTarget = useRef<string | null>(null);

  const readyDocs = useMemo(
    () => documents.filter((d) => d.status === 'ready' && !d.needs_reindex),
    [documents],
  );

  function toggle(projectId: string) {
    setExpanded((prev) => ({ ...prev, [projectId]: !prev[projectId] }));
  }

  function openUpload(projectId: string) {
    uploadTarget.current = projectId;
    uploadRef.current?.click();
  }

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-brand">
        <button type="button" className="header-dog" title="显示桌宠" aria-label="显示桌宠" onClick={onShowPet}>
          <DogAvatar state={petState} />
        </button>
        <div className="brand-copy">
          <strong>{petName}</strong>
          <span>陪你学一点</span>
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-head">
          <span className="sidebar-label">学习夹</span>
          <button type="button" className="sidebar-icon-btn" title="新建学习夹" disabled={busy} onClick={onCreateProject}>
            ＋
          </button>
        </div>
        <ul className="project-tree" aria-label="学习项目">
          {projects.map((project) => {
            const open = expanded[project.id] ?? activeProjectId === project.id;
            const isActive = activeProjectId === project.id;
            const available = readyDocs.filter((d) => !project.document_ids.includes(d.id));
            return (
              <li key={project.id} className={`project-node${isActive ? ' is-active' : ''}`}>
                <div className="project-row">
                  <button
                    type="button"
                    className={`project-chevron${open ? ' is-open' : ''}`}
                    aria-expanded={open}
                    onClick={() => toggle(project.id)}
                  >
                    <span className="chevron-mark" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="project-folder"
                    onClick={() => onSelectProject(project)}
                    title={project.name}
                  >
                    <span className="project-name">{project.name}</span>
                  </button>
                  <button
                    type="button"
                    className="sidebar-icon-btn quiet"
                    title="重命名"
                    onClick={() => onRenameProject(project)}
                  >
                    改名
                  </button>
                </div>
                {open && (
                  <ul className="project-files">
                    {project.files.map((file) => (
                      <li key={file.id} className="project-file">
                        <span className="file-name" title={file.filename}>
                          {file.filename}
                        </span>
                        <button
                          type="button"
                          className="sidebar-icon-btn quiet"
                          title="从学习夹移除"
                          onClick={() => onDetachFile(project.id, file.id)}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                    <li className="project-file-actions">
                      <button
                        type="button"
                        className="sidebar-link-btn"
                        disabled={busy}
                        onClick={() => setPickerFor(pickerFor === project.id ? null : project.id)}
                      >
                        从资料库加入
                      </button>
                      <button type="button" className="sidebar-link-btn" disabled={busy} onClick={() => openUpload(project.id)}>
                        上传文件
                      </button>
                    </li>
                    {pickerFor === project.id && (
                      <li className="project-picker">
                        {available.length === 0 ? (
                          <span className="muted">资料库暂无可加入文件</span>
                        ) : (
                          available.map((doc) => (
                            <button
                              key={doc.id}
                              type="button"
                              className="picker-item"
                              onClick={() => {
                                onAttachFile(project.id, doc.id);
                                setPickerFor(null);
                              }}
                            >
                              {doc.filename}
                            </button>
                          ))
                        )}
                      </li>
                    )}
                    {projects.length > 1 && (
                      <li>
                        <button type="button" className="sidebar-link-btn danger" onClick={() => onDeleteProject(project)}>
                          删除学习夹
                        </button>
                      </li>
                    )}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <nav className="sidebar-tools" aria-label="工具">
        {toolNav.map((item) => (
          <button
            key={item.key}
            type="button"
            className={tab === item.key ? 'active' : ''}
            onClick={() => onSelectTab(item.key)}
          >
            {item.label}
            {item.key === 'library' && libraryCount > 0 && <span className="tab-count">{libraryCount}</span>}
          </button>
        ))}
      </nav>

      <input
        ref={uploadRef}
        type="file"
        accept=".pdf,.docx,.pptx,.txt"
        multiple
        hidden
        onChange={(e) => {
          const target = uploadTarget.current;
          const files = e.target.files;
          if (target && files?.length) onUploadToProject(target, files);
          e.target.value = '';
        }}
      />
    </aside>
  );
}