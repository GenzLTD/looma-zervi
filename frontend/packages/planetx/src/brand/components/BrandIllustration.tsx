import type { ReactNode, CSSProperties } from 'react'

/**
 * BrandIllustration — 品牌插画组件
 *
 * 两层渲染：
 *   1. 如果图源已就绪（/<brand>/.../xxx.png 存在），展示 <img>
 *   2. 否则展示占位区域（品牌色渐变 + emoji/文字），设计师交付后自动切换
 *
 * 未加载成功时自动退化到 placeholder 模式。
 *
 * 用法：
 *   <BrandIllustration
 *     src="/brand/illustrations/planetx/galaxy_hero.png"
 *     placeholder="🌌"
 *     width={200}
 *     alt="深空星系"
 *   />
 */
interface BrandIllustrationProps {
  /** 图片路径 (public/ 下) */
  src: string
  /** 图片失败时展示的占位内容 */
  placeholder?: ReactNode
  /** 宽度 */
  width?: number | string
  /** 高度 */
  height?: number | string
  /** alt 文本 */
  alt?: string
  /** 占位背景渐变 */
  placeholderGradient?: string
  /** 占位文字 */
  placeholderText?: string
  /** 是否圆形裁切 */
  circular?: boolean
  style?: CSSProperties
  className?: string
}

export default function BrandIllustration({
  src,
  placeholder,
  width = '100%',
  height,
  alt = '',
  placeholderGradient = 'linear-gradient(135deg, var(--px-color-surface-card), var(--px-color-surface-root))',
  placeholderText,
  circular = false,
  style,
  className,
}: BrandIllustrationProps) {
  const borderRadius = circular ? '50%' : 'var(--lo-radius-lg)'

  // 占位区域
  const placeholderElement = placeholder ?? (
    <div
      style={{
        width: typeof width === 'number' ? width : '100%',
        height: height ?? (typeof width === 'number' ? width : 200),
        background: placeholderGradient,
        borderRadius,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--px-color-text-tertiary)',
        fontSize: placeholderText ? 'var(--lo-font-size-sm)' : 32,
      }}
    >
      {placeholderText ?? '🖼️'}
    </div>
  )

  return (
    <div
      className={className}
      style={{
        position: 'relative',
        width: typeof width === 'number' ? width : undefined,
        height: height,
        borderRadius,
        overflow: 'hidden',
        ...style,
      }}
    >
      {/* 占位层（始终存在，图片加载成功后被覆盖） */}
      {placeholderElement}

      {/* 真实图片层 */}
      <img
        src={src}
        alt={alt}
        loading="lazy"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          borderRadius,
          opacity: 0,
          transition: 'opacity 0.3s ease',
        }}
        onLoad={(e) => {
          e.currentTarget.style.opacity = '1'
        }}
        onError={(e) => {
          // 加载失败，保持 placeholder 可见
          e.currentTarget.style.display = 'none'
        }}
      />
    </div>
  )
}
