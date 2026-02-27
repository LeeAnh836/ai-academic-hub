/**
 * Create a cropped image from the provided image source and crop area
 */

export interface Area {
  x: number
  y: number
  width: number
  height: number
}

/**
 * Create a File object from a cropped area of an image
 * @param imageSrc - Source image URL
 * @param pixelCrop - Crop area in pixels
 * @param fileName - Name for the output file
 * @returns Promise<File> - The cropped image as a File object
 */
export async function getCroppedImg(
  imageSrc: string,
  pixelCrop: Area,
  fileName: string = 'cropped.jpg'
): Promise<File> {
  const image = await createImage(imageSrc)
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')

  if (!ctx) {
    throw new Error('Failed to get canvas context')
  }

  // Set canvas size to the crop size
  canvas.width = pixelCrop.width
  canvas.height = pixelCrop.height

  // Draw the cropped image
  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    pixelCrop.width,
    pixelCrop.height
  )

  // Convert canvas to blob then to File
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('Canvas is empty'))
        return
      }
      const file = new File([blob], fileName, { type: 'image/jpeg' })
      resolve(file)
    }, 'image/jpeg', 0.95)
  })
}

/**
 * Helper function to create an image object from a URL
 */
function createImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.addEventListener('load', () => resolve(image))
    image.addEventListener('error', (error) => reject(error))
    image.src = url
  })
}
