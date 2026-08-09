import BrandIllustration from '../../brand/components/BrandIllustration'

/**
 * BrandAvatar — 品牌头像组件
 *
 * 封装 BrandIllustration，固定为圆形 + 头像默认占位。
 * 图片未加载时使用首字母 + 品牌渐变的 fallback。
 */
interface BrandAvatarProps {
  src?: string
  name: string
  size?: number
}

export default function BrandAvatar({ src, name, size = 48 }: BrandAvatarProps) {
  const initial = name.charAt(0).toUpperCase()

  if (!src) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--px-color-brand), rgba(0,212,255,0.6))',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 800,
          fontSize: size * 0.38,
          flexShrink: 0,
        }}
      >
        {initial}
      </div>
    )
  }

  return (
    <BrandIllustration
      src={src}
      width={size}
      height={size}
      circular
      alt={`${name} 头像`}
      placeholder={
        <div
          style={{
            width: size,
            height: size,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--px-color-brand), rgba(0,212,255,0.6))',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 800,
            fontSize: size * 0.38,
          }}
        >
          {initial}
        </div>
      }
    />
  )
}
