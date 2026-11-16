import { useMemo, useRef, useState } from 'react';
import { DogAvatar } from './DogAvatar';
import type { KnowledgeDocument, LearningProject } from './knowledge';
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
  const [addFor, setAddFor] = useState<string | null>(null);
  const [editFor, setEditFor] = useState<string | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const uploadTarget = useRef<string | null>(null);

  const readyDocs = useMemo(
    () => documents.filter((d) => d.status === 'ready' && !d.needs_reindex),
    [documents],
  );

  function openUpload(projectId: string) {
    uploadTarget.current = projectId;
    uploadRef.current?.click();
    setAddFor(null);
  }

  function activateFolder(project: LearningProject) {
    onSelectProject(project);
    const open = expanded[project.id] ?? activeProjectId === project.id;
    setExpanded((prev) => ({ ...prev, [project.id]: !open }));
  }

  return (
    <aside className="app-sidebar app-sidebar--cursor">
      <div className="app-sidebar-brand">
        <button type="button" className="header-dog" title="显示桌宠" aria-label="显示桌宠" onClick={onShowPet}>
          <DogAvatar state={petState} />
        </button>
        <div className="brand-copy">
          <strong>{petName}</strong>
          <span>学习助手</span>
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-head sidebar-section-head--cursor">
          <span className="sidebar-label">学习夹</span>
          <div className="sidebar-section-tools">
            <button
              type="button"
              className="tree-tool-btn"
              title="新建学习夹"
              aria-label="新建学习夹"
              disabled={busy}
              onClick={onCreateProject}
            >
              <span className="tree-tool-icon tree-tool-icon-new" aria-hidden="true" />
            </button>
          </div>
        </div>
        <ul className="project-tree" aria-label="学习项目">
          {projects.map((project) => {
            const open = expanded[project.id] ?? activeProjectId === project.id;
            const isActive = activeProjectId === project.id;
            const available = readyDocs.filter((d) => !project.document_ids.includes(d.id));
            return (
              <li
                key={project.id}
                className={`project-node${isActive ? ' is-active' : ''}${open ? ' is-open' : ''}`}
              >
                <div className="tree-folder-row">
                  <button
                    type="button"
                    className="tree-folder-main"
                    aria-expanded={open}
                    title={project.name}
                    onClick={() => activateFolder(project)}
                  >
                    {open ? (
                      <span className="tree-chevron is-expanded" aria-hidden="true" />
                    ) : (
                      <span className="tree-glyph tree-glyph-folder" aria-hidden="true" />
                    )}
                    <span className="tree-folder-label">{project.name}</span>
                    {project.files.length > 0 && !open ? (
                      <span className="tree-folder-meta">{project.files.length}</span>
                    ) : null}
                  </button>
                  <div className="tree-row-actions">
                    <button
                      type="button"
                      className="tree-icon-btn"
                      title="编辑学习夹"
                      aria-label={`编辑 ${project.name}`}
                      aria-expanded={editFor === project.id}
                      disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!open) setExpanded((prev) => ({ ...prev, [project.id]: true }));
                        setEditFor((cur) => (cur === project.id ? null : project.id));
                        setAddFor(null);
                        setPickerFor(null);
                      }}
                    >
                      <span className="tree-icon tree-icon-pencil" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      className="tree-icon-btn"
                      title="添加文件"
                      aria-label={`向 ${project.name} 添加文件`}
                      aria-expanded={addFor === project.id}
                      disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!open) setExpanded((prev) => ({ ...prev, [project.id]: true }));
                        setAddFor((cur) => (cur === project.id ? null : project.id));
                        setEditFor(null);
                        setPickerFor(null);
                      }}
                    >
                      <span className="tree-icon tree-icon-plus" aria-hidden="true" />
                    </button>
                  </div>
                </div>
                {open && (
                  <ul className="tree-children">
                    {project.files.length === 0 && addFor !== project.id && !pickerFor && editFor !== project.id ? (
                      <li className="tree-empty-files muted">暂无文件</li>
                    ) : null}
                    {project.files.map((file) => (
                      <li key={file.id}>
                        <div className="tree-file-row">
                          <span className="tree-glyph tree-glyph-file" aria-hidden="true" />
                          <span className="tree-file-name" title={file.filename}>
                            {file.filename}
                          </span>
                          <button
                            type="button"
                            className="tree-action"
                            title="从学习夹移除"
                            aria-label={`移除 ${file.filename}`}
                            onClick={() => onDetachFile(project.id, file.id)}
                          >
                            ×
                          </button>
                        </div>
                      </li>
                    ))}
                    {editFor === project.id ? (
                      <li className="tree-edit-menu">
                        <button
                          type="button"
                          className="sidebar-link-btn"
                          disabled={busy}
                          onClick={() => {
                            setEditFor(null);
                            onRenameProject(project);
                          }}
                        >
                          重命名
                        </button>
                        {projects.length > 1 ? (
                          <button
                            type="button"
                            className="sidebar-link-btn danger"
                            disabled={busy}
                            onClick={() => {
                              setEditFor(null);
                              onDeleteProject(project);
                            }}
                          >
                            删除学习夹
                          </button>
                        ) : (
                          <span className="muted tree-menu-hint">至少保留一个学习夹</span>
                        )}
                      </li>
                    ) : null}
                    {addFor === project.id ? (
                      <li className="tree-add-menu">
                        <button
                          type="button"
                          className="sidebar-link-btn"
                          disabled={busy}
                          onClick={() => openUpload(project.id)}
                        >
                          上传文件
                        </button>
                        <button
                          type="button"
                          className="sidebar-link-btn"
                          disabled={busy}
                          onClick={() => {
                            setPickerFor(pickerFor === project.id ? null : project.id);
                            setAddFor(null);
                          }}
                        >
                          从资料库加入
                        </button>
                      </li>
                    ) : null}
                    {pickerFor === project.id ? (
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
                    ) : null}
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
            {item.key === 'library' && libraryCount > 0 ? (
              <span className="tab-count">{libraryCount}</span>
            ) : null}
          </button>
        ))}
      </nav>

      <p className="sidebar-footer-note">资料与对话保存在本机</p>

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