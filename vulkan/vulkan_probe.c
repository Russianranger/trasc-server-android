/* App-private Vulkan device + X11 swapchain preflight. No game assets. */
#define VK_USE_PLATFORM_XLIB_KHR
#include <vulkan/vulkan.h>
#include <X11/Xlib.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define CHECK(call) do { VkResult result_ = (call); if (result_ != VK_SUCCESS) { \
    fprintf(stderr, "%s failed: VkResult %d (line %d)\n", #call, result_, __LINE__); return 1; } } while (0)
static void json_string(const char *s) {
    putchar('"');
    for (const unsigned char *p=(const unsigned char *)s; *p; ++p) {
        if (*p=='"' || *p=='\\') printf("\\%c",*p);
        else if (*p<32) printf("\\u%04x",*p);
        else putchar(*p);
    }
    putchar('"');
}
int main(int argc, char **argv) {
    /* Software is permitted only in explicit CI invocations, never by device fallback. */
    int allow_software=argc==2 && !strcmp(argv[1],"--allow-software");
    const char *extensions[]={VK_KHR_SURFACE_EXTENSION_NAME,VK_KHR_XLIB_SURFACE_EXTENSION_NAME};
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="TRASC Vulkan preflight",.apiVersion=VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app,.enabledExtensionCount=2,.ppEnabledExtensionNames=extensions};
    VkInstance instance; CHECK(vkCreateInstance(&ici,NULL,&instance));
    uint32_t count=0; CHECK(vkEnumeratePhysicalDevices(instance,&count,NULL));
    if (!count || count>32) {fprintf(stderr,"No usable Vulkan device; check Turnip and /dev/kgsl-3d0 access\n");return 1;}
    VkPhysicalDevice physicals[32]; CHECK(vkEnumeratePhysicalDevices(instance,&count,physicals));
    VkPhysicalDevice physical=VK_NULL_HANDLE;
    VkPhysicalDeviceDriverProperties driver={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
    VkPhysicalDeviceProperties2 properties={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=&driver};
    for (uint32_t i=0;i<count;i++) {
        vkGetPhysicalDeviceProperties2(physicals[i],&properties);
        if ((driver.driverID==VK_DRIVER_ID_MESA_TURNIP && properties.properties.vendorID==0x5143 && properties.properties.deviceType!=VK_PHYSICAL_DEVICE_TYPE_CPU) ||
            (allow_software && properties.properties.deviceType==VK_PHYSICAL_DEVICE_TYPE_CPU)) {physical=physicals[i];break;}
    }
    if (!physical) {fprintf(stderr,"Turnip/Qualcomm hardware was not enumerated; software fallback rejected\n");return 1;}
    if (properties.properties.apiVersion<VK_API_VERSION_1_3) {fprintf(stderr,"Vulkan 1.3 required for DXVK 2.5.3\n");return 1;}
    Display *display=XOpenDisplay(NULL);
    if (!display) {fprintf(stderr,"Private X11 display unavailable\n");return 1;}
    Window window=XCreateSimpleWindow(display,DefaultRootWindow(display),0,0,64,64,0,0,0);
    XStoreName(display,window,"TRASC Vulkan check");XMapWindow(display,window);XSync(display,False);
    VkXlibSurfaceCreateInfoKHR sci={.sType=VK_STRUCTURE_TYPE_XLIB_SURFACE_CREATE_INFO_KHR,.dpy=display,.window=window};
    VkSurfaceKHR surface; CHECK(vkCreateXlibSurfaceKHR(instance,&sci,NULL,&surface));
    uint32_t qcount=0;vkGetPhysicalDeviceQueueFamilyProperties(physical,&qcount,NULL);
    if (!qcount || qcount>64) return 1;
    VkQueueFamilyProperties queues[64];vkGetPhysicalDeviceQueueFamilyProperties(physical,&qcount,queues);
    uint32_t family=UINT32_MAX;
    for (uint32_t i=0;i<qcount;i++) {VkBool32 present=0;CHECK(vkGetPhysicalDeviceSurfaceSupportKHR(physical,i,surface,&present));if(present&&(queues[i].queueFlags&VK_QUEUE_GRAPHICS_BIT)){family=i;break;}}
    if (family==UINT32_MAX) {fprintf(stderr,"No graphics queue can present to the private display\n");return 1;}
    float priority=1.0f;
    VkDeviceQueueCreateInfo qci={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};
    const char *device_extensions[]={VK_KHR_SWAPCHAIN_EXTENSION_NAME};
    VkDeviceCreateInfo dci={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qci,.enabledExtensionCount=1,.ppEnabledExtensionNames=device_extensions};
    VkDevice device;CHECK(vkCreateDevice(physical,&dci,NULL,&device));VkQueue queue;vkGetDeviceQueue(device,family,0,&queue);
    VkSurfaceCapabilitiesKHR caps;CHECK(vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical,surface,&caps));
    count=0;CHECK(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&count,NULL));if(!count||count>256)return 1;
    VkSurfaceFormatKHR formats[256];CHECK(vkGetPhysicalDeviceSurfaceFormatsKHR(physical,surface,&count,formats));
    VkSurfaceFormatKHR format=formats[0];
    for(uint32_t i=0;i<count;i++)if(formats[i].format==VK_FORMAT_B8G8R8A8_UNORM){format=formats[i];break;}
    if(format.format==VK_FORMAT_UNDEFINED)format.format=VK_FORMAT_B8G8R8A8_UNORM;
    VkExtent2D extent=caps.currentExtent.width==UINT32_MAX?(VkExtent2D){64,64}:caps.currentExtent;
    uint32_t images=caps.minImageCount+1;if(caps.maxImageCount&&images>caps.maxImageCount)images=caps.maxImageCount;
    VkCompositeAlphaFlagBitsKHR alpha=(VkCompositeAlphaFlagBitsKHR)(caps.supportedCompositeAlpha&(~caps.supportedCompositeAlpha+1));
    if(!(caps.supportedUsageFlags&VK_IMAGE_USAGE_TRANSFER_DST_BIT))return 1;
    VkSwapchainCreateInfoKHR swapci={.sType=VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,.surface=surface,.minImageCount=images,.imageFormat=format.format,.imageColorSpace=format.colorSpace,.imageExtent=extent,.imageArrayLayers=1,.imageUsage=VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,.imageSharingMode=VK_SHARING_MODE_EXCLUSIVE,.preTransform=caps.currentTransform,.compositeAlpha=alpha,.presentMode=VK_PRESENT_MODE_FIFO_KHR,.clipped=VK_TRUE};
    VkSwapchainKHR swapchain;CHECK(vkCreateSwapchainKHR(device,&swapci,NULL,&swapchain));
    count=0;CHECK(vkGetSwapchainImagesKHR(device,swapchain,&count,NULL));if(!count||count>16)return 1;
    VkImage image[16];CHECK(vkGetSwapchainImagesKHR(device,swapchain,&count,image));
    VkCommandPoolCreateInfo pci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=family};
    VkCommandPool pool;CHECK(vkCreateCommandPool(device,&pci,NULL,&pool));
    VkCommandBufferAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
    VkCommandBuffer command;CHECK(vkAllocateCommandBuffers(device,&ai,&command));
    VkFenceCreateInfo fci={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VkFence fence;CHECK(vkCreateFence(device,&fci,NULL,&fence));
    VkImageSubresourceRange range={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    for(uint32_t frame=0;frame<3;frame++) {
        uint32_t index;CHECK(vkAcquireNextImageKHR(device,swapchain,5000000000ULL,VK_NULL_HANDLE,fence,&index));
        CHECK(vkWaitForFences(device,1,&fence,VK_TRUE,5000000000ULL));CHECK(vkResetFences(device,1,&fence));
        CHECK(vkResetCommandBuffer(command,0));VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};CHECK(vkBeginCommandBuffer(command,&begin));
        VkImageMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=image[index],.subresourceRange=range};
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&barrier);
        VkClearColorValue color={.float32={0.05f,0.5f,0.25f,1.0f}};vkCmdClearColorImage(command,image[index],VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&color,1,&range);
        barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;barrier.dstAccessMask=0;barrier.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;barrier.newLayout=VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,0,0,NULL,0,NULL,1,&barrier);
        CHECK(vkEndCommandBuffer(command));VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&command};CHECK(vkQueueSubmit(queue,1,&submit,fence));
        CHECK(vkWaitForFences(device,1,&fence,VK_TRUE,5000000000ULL));CHECK(vkResetFences(device,1,&fence));
        VkPresentInfoKHR present={.sType=VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,.swapchainCount=1,.pSwapchains=&swapchain,.pImageIndices=&index};CHECK(vkQueuePresentKHR(queue,&present));
        XSync(display,False);usleep(50000);
    }
    CHECK(vkDeviceWaitIdle(device));
    printf("{\"device\":");json_string(properties.properties.deviceName);printf(",\"driver\":");json_string(driver.driverName);
    printf(",\"driver_id\":%u,\"vendor_id\":%u,\"api_version\":%u,\"software\":%s,\"presentation_frames\":3}\n",driver.driverID,properties.properties.vendorID,properties.properties.apiVersion,properties.properties.deviceType==VK_PHYSICAL_DEVICE_TYPE_CPU?"true":"false");
    vkDestroyFence(device,fence,NULL);vkDestroyCommandPool(device,pool,NULL);vkDestroySwapchainKHR(device,swapchain,NULL);vkDestroyDevice(device,NULL);vkDestroySurfaceKHR(instance,surface,NULL);vkDestroyInstance(instance,NULL);XDestroyWindow(display,window);XCloseDisplay(display);return 0;
}
