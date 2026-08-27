import type { Meta, StoryObj } from "@storybook/react";
import {
  PlanetXModal,
  PlanetXDropdown,
  PlanetXTabs,
  PlanetXChatBubble,
  PlanetXStreamingText,
  PlanetXTooltip,
  PlanetXIcon,
} from "../index";
import PlanetXButton from "../PlanetXButton";
import type { PlanetXIconName } from "../PlanetXIcon";
import { ICON_GLYPHS } from "../icons/glyphs";

const meta: Meta = {
  title: "PlanetX/New Components",
  parameters: {
    layout: "centered",
  },
};

export default meta;

// Modal 组件示例
export const ModalExample: StoryObj = {
  render: () => {
    const [isOpen, setIsOpen] = useState(false);
    
    return (
      <div>
        <PlanetXButton onClick={() => setIsOpen(true)}>
          Open Modal
        </PlanetXButton>
        
        <PlanetXModal
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
          title="Mission Details"
          size="md"
        >
          <div style={{ padding: "var(--px-spacing-md)" }}>
            <h3 style={{ marginBottom: "var(--px-spacing-sm)" }}>Daily Quest</h3>
            <p style={{ 
              color: "var(--px-color-text-muted)",
              marginBottom: "var(--px-spacing-md)" 
            }}>
              Complete 5 AI chat sessions to earn 100 XP and unlock the "AI Explorer" badge.
            </p>
            
            <div style={{ 
              display: "flex", 
              gap: "var(--px-spacing-sm)",
              justifyContent: "flex-end"
            }}>
              <PlanetXButton variant="ghost" onClick={() => setIsOpen(false)}>
                Cancel
              </PlanetXButton>
              <PlanetXButton variant="primary">
                Accept Quest
              </PlanetXButton>
            </div>
          </div>
        </PlanetXModal>
      </div>
    );
  },
};

// Dropdown 组件示例
export const DropdownExample: StoryObj = {
  render: () => {
    const items = [
      { value: "profile", label: "Profile", icon: <PlanetXIcon name="profile" size={14} /> },
      { value: "settings", label: "Settings", icon: <PlanetXIcon name="settings" size={14} /> },
      { value: "achievements", label: "Achievements", icon: <PlanetXIcon name="trophy" size={14} /> },
      { value: "logout", label: "Log Out", icon: <PlanetXIcon name="logout" size={14} /> },
    ];

    return (
      <PlanetXDropdown
        trigger={
          <PlanetXButton variant="ghost" rightIcon={<PlanetXIcon name="chevron-down" size={14} />}>
            User Menu
          </PlanetXButton>
        }
        items={items}
        onSelect={(value) => console.log("Selected:", value)}
        align="right"
        width="180px"
      />
    );
  },
};

// Tabs 组件示例
export const TabsExample: StoryObj = {
  render: () => {
    const [activeTab, setActiveTab] = useState("quests");
    
    const tabs = [
      { value: "quests", label: "Quests", badge: "3" },
      { value: "achievements", label: "Achievements", badge: "12" },
      { value: "leaderboard", label: "Leaderboard" },
      { value: "shop", label: "Shop" },
    ];

    return (
      <div style={{ width: "400px" }}>
        <PlanetXTabs
          items={tabs}
          activeTab={activeTab}
          onChange={setActiveTab}
          variant="default"
          fullWidth
        />
        
        <div style={{ 
          marginTop: "var(--px-spacing-xl)",
          padding: "var(--px-spacing-lg)",
          background: "var(--px-color-bg-surface)",
          borderRadius: "var(--px-radius-lg)"
        }}>
          {activeTab === "quests" && (
            <div>
              <h3>Active Quests</h3>
              <p>Complete daily challenges to earn rewards!</p>
            </div>
          )}
          {activeTab === "achievements" && (
            <div>
              <h3>Your Achievements</h3>
              <p>Unlocked 12 out of 50 achievements.</p>
            </div>
          )}
          {activeTab === "leaderboard" && (
            <div>
              <h3>Global Ranking</h3>
              <p>You're ranked #42 worldwide!</p>
            </div>
          )}
          {activeTab === "shop" && (
            <div>
              <h3>Item Shop</h3>
              <p>Exchange XP for exclusive items.</p>
            </div>
          )}
        </div>
      </div>
    );
  },
};

// 垂直标签页示例
export const VerticalTabs: StoryObj = {
  render: () => {
    const [activeTab, setActiveTab] = useState("profile");
    
    const tabs = [
      { value: "profile", label: "Profile", icon: "👤" },
      { value: "notifications", label: "Notifications", icon: "🔔", badge: "5" },
      { value: "privacy", label: "Privacy", icon: "🔒" },
      { value: "billing", label: "Billing", icon: "💳" },
    ];

    return (
      <div style={{ display: "flex", height: "300px" }}>
        <div style={{ width: "200px", marginRight: "var(--px-spacing-xl)" }}>
          <PlanetXTabs
            items={tabs}
            activeTab={activeTab}
            onChange={setActiveTab}
            variant="pills"
            orientation="vertical"
          />
        </div>
        
        <div style={{ 
          flex: 1,
          padding: "var(--px-spacing-lg)",
          background: "var(--px-color-bg-surface)",
          borderRadius: "var(--px-radius-lg)"
        }}>
          <h3>{tabs.find(t => t.value === activeTab)?.label} Settings</h3>
          <p>Configure your {activeTab} preferences here.</p>
        </div>
      </div>
    );
  },
};

// 组件组合示例
export const ComponentComposition: StoryObj = {
  render: () => {
    const [modalOpen, setModalOpen] = useState(false);
    const [activeTab, setActiveTab] = useState("general");
    
    const dropdownItems = [
      { value: "edit", label: "Edit Mission", icon: "✏️" },
      { value: "duplicate", label: "Duplicate", icon: "📋" },
      { value: "archive", label: "Archive", icon: "📁" },
      { value: "delete", label: "Delete", icon: "🗑️" },
    ];

    const tabs = [
      { value: "general", label: "General" },
      { value: "rewards", label: "Rewards" },
      { value: "requirements", label: "Requirements" },
    ];

    return (
      <div style={{ 
        maxWidth: "600px",
        margin: "0 auto",
        padding: "var(--px-spacing-xl)",
        background: "var(--px-color-bg-deep)",
        borderRadius: "var(--px-radius-xl)"
      }}>
        <div style={{ 
          display: "flex", 
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "var(--px-spacing-lg)"
        }}>
          <h2 style={{ margin: 0 }}>Mission Configuration</h2>
          
          <PlanetXDropdown
            trigger={
              <PlanetXButton variant="outline" size="sm">
                Actions ▼
              </PlanetXButton>
            }
            items={dropdownItems}
            onSelect={(value) => {
              if (value === "delete") {
                setModalOpen(true);
              }
            }}
            align="right"
          />
        </div>
        
        <PlanetXTabs
          items={tabs}
          activeTab={activeTab}
          onChange={setActiveTab}
          variant="default"
          fullWidth
          style={{ marginBottom: "var(--px-spacing-lg)" }}
        />
        
        <div style={{ 
          padding: "var(--px-spacing-lg)",
          background: "var(--px-color-bg-surface)",
          borderRadius: "var(--px-radius-lg)",
          marginBottom: "var(--px-spacing-lg)"
        }}>
          {activeTab === "general" && (
            <div>
              <h3>General Settings</h3>
              <p>Configure basic mission parameters.</p>
            </div>
          )}
          {activeTab === "rewards" && (
            <div>
              <h3>Rewards Configuration</h3>
              <p>Set XP, badges, and other rewards.</p>
            </div>
          )}
          {activeTab === "requirements" && (
            <div>
              <h3>Requirements</h3>
              <p>Define completion criteria.</p>
            </div>
          )}
        </div>
        
        <div style={{ 
          display: "flex", 
          gap: "var(--px-spacing-sm)",
          justifyContent: "flex-end"
        }}>
          <PlanetXButton variant="ghost">
            Cancel
          </PlanetXButton>
          <PlanetXButton variant="primary">
            Save Changes
          </PlanetXButton>
        </div>
        
        <PlanetXModal
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Delete Mission"
          size="sm"
        >
          <div style={{ padding: "var(--px-spacing-md)" }}>
            <p style={{ 
              color: "var(--px-color-text)",
              marginBottom: "var(--px-spacing-lg)"
            }}>
              Are you sure you want to delete this mission? This action cannot be undone.
            </p>
            
            <div style={{ 
              display: "flex", 
              gap: "var(--px-spacing-sm)",
              justifyContent: "flex-end"
            }}>
              <PlanetXButton variant="ghost" onClick={() => setModalOpen(false)}>
                Cancel
              </PlanetXButton>
              <PlanetXButton variant="danger">
                Delete
              </PlanetXButton>
            </div>
          </div>
        </PlanetXModal>
      </div>
    );
  },
};

export const ChatBubbleExample: StoryObj = {
  render: () => (
    <div style={{ width: 420 }}>
      <PlanetXChatBubble role="user" content="星系匹配结果怎么样？" />
      <PlanetXChatBubble
        role="ai"
        content="你的适配度 87%。舰队已为你锁定 3 个高潜岗位。"
        timestamp="刚刚"
      />
      <PlanetXChatBubble role="ai" content="" loading />
    </div>
  ),
};

export const StreamingTextExample: StoryObj = {
  render: () => (
    <div style={{ width: 360, color: "var(--px-color-text)" }}>
      <PlanetXStreamingText text="正在解析你的星际档案" done={false} />
    </div>
  ),
};

export const TooltipExample: StoryObj = {
  render: () => (
    <div style={{ display: "flex", gap: "var(--px-spacing-xl)" }}>
      <PlanetXTooltip content="深空提示：完成每日任务可获得 XP" position="top">
        <PlanetXButton variant="outline">悬停查看</PlanetXButton>
      </PlanetXTooltip>
      <PlanetXTooltip content="右侧提示" position="right">
        <PlanetXButton variant="ghost">右侧</PlanetXButton>
      </PlanetXTooltip>
    </div>
  ),
};

export const IconSystemExample: StoryObj = {
  render: () => {
    const names = Object.keys(ICON_GLYPHS) as PlanetXIconName[];
    return (
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(100px, 1fr))",
          gap: "var(--px-spacing-md)",
          width: 480,
          color: "var(--px-color-accent)",
        }}
      >
        {names.map((name) => (
          <div
            key={name}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 8,
              padding: "var(--px-spacing-sm)",
              borderRadius: "var(--px-radius-md)",
              background: "var(--px-color-bg-surface)",
              border: "1px solid var(--px-border-default)",
            }}
          >
            <PlanetXIcon name={name} size={24} color="currentColor" />
            <span style={{ fontSize: 11, color: "var(--px-color-text-muted)" }}>{name}</span>
          </div>
        ))}
      </div>
    );
  },
};

// 辅助函数和状态管理
import { useState } from "react";